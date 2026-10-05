-- Arc Raiders Blueprint Goblin — Phase 3 Stage B schema.
--
-- Run this once in the Supabase SQL Editor for the project. There's no CI
-- auto-deploy for this (GitHub integration was skipped when the project was
-- created), so this file is the source of truth but has to be applied by
-- hand — checked in for review/history, not for automatic execution.
--
-- One row per local install (one row per anonymous-auth user). `select` is
-- public (a friend needs to be able to look up your row by Goblin ID/SteamID
-- without any relationship being established first) but `insert`/`update`
-- are restricted to the row's own auth.uid(). There is no `delete`
-- policy/grant on purpose — "Wipe Cloud Data" clears the array columns via
-- `update` rather than removing the row, so a friend's lookup doesn't start
-- erroring for someone who wiped their cloud data.

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  arbg_user_id text not null unique,
  steam_id text,
  blueprints_owned integer[] not null default '{}',
  blueprints_wanted integer[] not null default '{}',
  blueprints_spare integer[] not null default '{}',
  updated_at timestamptz not null default now()
);

create index profiles_steam_id_idx on public.profiles (steam_id) where steam_id is not null;

alter table public.profiles enable row level security;

create policy "Profiles are publicly readable"
  on public.profiles for select
  using (true);

create policy "Users can insert their own profile"
  on public.profiles for insert
  with check (auth.uid() = id);

create policy "Users can update their own profile"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Required because "Automatically expose new tables" was deliberately left
-- off during project creation — RLS alone doesn't make the Data API serve a
-- table, these grants do.
grant usage on schema public to anon, authenticated;
grant select, insert, update on public.profiles to anon, authenticated;

-- Steam Web API proxy rate limiting (supabase/functions/steam-*) — added
-- when the app moved off per-user "bring your own Steam Web API key"
-- (Valve requires a phone number + non-"limited" account to generate one,
-- a real adoption blocker) to a shared server-side key. One key now serves
-- every user, so a per-user daily cap exists to stop a runaway bug or
-- deliberate abuse from draining the shared key's quota or getting it
-- flagged by Valve.
--
-- Only ever touched by the service_role key from inside the Edge Functions
-- themselves (which bypasses RLS entirely) — no grants to anon/authenticated
-- on this table on purpose, so it's fully inaccessible to any client
-- directly, only reachable through increment_steam_proxy_usage() below.
create table public.steam_proxy_usage (
  user_id uuid not null references auth.users (id) on delete cascade,
  day date not null default current_date,
  call_count integer not null default 0,
  primary key (user_id, day)
);

alter table public.steam_proxy_usage enable row level security;

-- Atomic upsert-and-return-new-count in one statement — a separate
-- read-then-write from the Edge Function would let two near-simultaneous
-- calls from the same user both read the same starting count and
-- under-count each other.
create or replace function public.increment_steam_proxy_usage(p_user_id uuid)
returns integer
language sql
security definer
set search_path = public
as $$
  insert into public.steam_proxy_usage (user_id, day, call_count)
  values (p_user_id, current_date, 1)
  on conflict (user_id, day)
  do update set call_count = steam_proxy_usage.call_count + 1
  returning call_count;
$$;

-- p_user_id is caller-supplied, not derived from auth.uid() inside the
-- function, so exposing this to anon/authenticated would let any user
-- inflate any *other* user's counter (e.g. to grief them over the cap).
-- Only the service_role-authenticated Edge Function should ever call this.
revoke all on function public.increment_steam_proxy_usage(uuid) from public;
grant execute on function public.increment_steam_proxy_usage(uuid) to service_role;

-- Orphaned-profile reclaim + stale-row cleanup — added after a real user hit
-- `duplicate key value violates unique constraint "profiles_arbg_user_id_key"`
-- on Sync. Cause: arbg_user_id (the local, human-shared "Goblin ID") has its
-- own separate unique constraint from the id primary key. If a local
-- install's supabase_session.json is ever lost/reset while config.json (and
-- therefore arbg_user_id) survives, the next sync mints a fresh auth.uid()
-- and tries to insert a row under the *same* arbg_user_id as before,
-- colliding with the old row -- still sitting there under the now
-- unreachable old auth.uid().
--
-- A naive reclaim (just re-parenting any row matching an arbg_user_id onto
-- whoever asks) would be a real security regression, not just a bug fix:
-- arbg_user_id is public by design (the friend-lookup feature depends on
-- looking a row up by Goblin ID), so anyone could hijack any *active* row
-- just by knowing its Goblin ID -- something today's auth.uid()-gated RLS
-- strictly prevents. Reclaim here is instead gated on proving knowledge of a
-- second, never-shared local secret via a server-side hash comparison.

-- STEP 0 (run first, by hand, before anything below): confirm where
-- pgcrypto/pg_cron actually live on this project rather than assuming --
--   select extname, extnamespace::regnamespace::text as schema
--   from pg_extension where extname in ('pgcrypto', 'pg_cron');
-- Enable whichever is missing:
--   create extension if not exists pgcrypto with schema extensions;
--   create extension if not exists pg_cron;
-- (or via Dashboard -> Database -> Extensions if a permission error blocks
-- the SQL form) and adjust the `extensions.` qualification below if the
-- real schema differs.

-- updated_at previously only defaulted on INSERT -- push_profile's payload
-- never sets it and there was no trigger, so an existing row's updated_at
-- was frozen at its original creation time forever. Needed so the
-- staleness-based cleanup below means anything.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row
execute function public.set_updated_at();

alter table public.profiles add column recovery_secret_hash text;

-- Hashes and stores the secret on the CALLER's own row only (id = auth.uid())
-- -- this alone is already as safe as any other authenticated write to your
-- own row. The "recovery_secret_hash is null" guard means it only ever sets
-- once and never overwrites an existing hash, so it's safe to call
-- unconditionally after every successful push rather than needing "is this
-- the first sync ever" logic client-side. gen_salt('bf', 10) is standard
-- bcrypt work-factor hardening; not actually load-bearing here since the
-- input is a 32-character random secret, not a guessable human password.
create or replace function public.set_recovery_secret(p_arbg_user_id text, p_secret text)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  if auth.uid() is null then
    return;
  end if;

  update public.profiles
  set recovery_secret_hash = extensions.crypt(p_secret, extensions.gen_salt('bf', 10))
  where id = auth.uid()
    and arbg_user_id = p_arbg_user_id
    and recovery_secret_hash is null;
end;
$$;

revoke all on function public.set_recovery_secret(text, text) from public;
grant execute on function public.set_recovery_secret(text, text) to authenticated;

-- Re-parents an orphaned row (arbg_user_id matches, id doesn't) onto the
-- caller's current auth.uid(), but only if p_secret matches the row's
-- stored hash. One atomic UPDATE, not select-then-update -- a separate read
-- would leave a TOCTOU window between checking the secret and re-parenting.
-- The "not exists (caller already owns a row)" guard means this cleanly
-- returns false instead of ever raising a raw profiles_pkey violation if
-- the caller somehow already has their own row.
--
-- Not brute-forceable: a 32-character secret from a 32-character alphabet
-- is ~1.46x10^48 possibilities, independent of and much larger than the
-- public Goblin ID's own keyspace -- knowing/guessing the public ID grants
-- nothing without the actual secret.
create or replace function public.reclaim_profile(p_arbg_user_id text, p_secret text)
returns boolean
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_row_count integer;
begin
  if auth.uid() is null then
    return false;
  end if;

  update public.profiles
  set id = auth.uid()
  where arbg_user_id = p_arbg_user_id
    and id <> auth.uid()
    and recovery_secret_hash is not null
    and extensions.crypt(p_secret, recovery_secret_hash) = recovery_secret_hash
    and not exists (
      select 1 from public.profiles p2 where p2.id = auth.uid()
    );

  get diagnostics v_row_count = row_count;
  return v_row_count > 0;
end;
$$;

revoke all on function public.reclaim_profile(text, text) from public;
grant execute on function public.reclaim_profile(text, text) to authenticated;

-- Both functions above are granted to `authenticated` only, not `anon` --
-- both no-op when auth.uid() is null, so granting to anon would be dead
-- weight, not a real hardening measure.

-- Scheduled cleanup for rows nobody ever reclaims -- 180 days of zero
-- activity is generous enough that no realistic casual player gets caught
-- out just for not opening the app in a while; this is irreversible
-- deletion, so erring long is the safer default for a first pass. Safe
-- w.r.t. other local state: arbg_friend_user_ids/arbg_active_friend_ids are
-- local-only, never in push_profile's payload -- a friend's row
-- disappearing just means their tile stops showing up in the next
-- friend-overlay refresh, no dangling reference anywhere else.
create or replace function public.delete_stale_profiles()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_deleted integer;
begin
  delete from public.profiles
  where updated_at < now() - interval '180 days'
     or obsoleted_at is not null;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;

-- No grants to anon/authenticated -- only ever invoked by the pg_cron job
-- below, which runs as the role that scheduled it.
revoke all on function public.delete_stale_profiles() from public;

select cron.schedule(
  'delete-stale-profiles',
  '0 6 * * *',
  $$select public.delete_stale_profiles();$$
);

-- Verified Steam-ID duplicate consolidation — added after repeated test
-- builds (fresh folders, no config.json) each minted a new Goblin ID, then
-- got linked to the same real Steam account, leaving multiple profiles rows
-- sharing one steam_id. A naive "consolidate by steam_id" action would be a
-- real security hole (worse than the arbg_user_id one reclaim_profile
-- guards against): SteamID64s are usually publicly discoverable, so
-- anything gated only on a client-claimed steam_id would let anyone obsolete
-- any other active user's row. This column is only ever written by
-- supabase/functions/consolidate-steam-profiles, which independently
-- re-verifies a Steam OpenID assertion server-side (re-running the same
-- check_authentication call the desktop app already does client-side)
-- before touching anything -- see that function for the actual gating.
alter table public.profiles add column obsoleted_at timestamptz;

-- The two other privileged-write features (increment_steam_proxy_usage,
-- reclaim_profile) both go through a `security definer` RPC, so they never
-- needed the service_role calling identity itself to hold table grants --
-- it runs as the function owner instead. This feature's Edge Function
-- updates public.profiles directly via a service-role postgrest client, so
-- it actually needs the grant: RLS bypass and table-level privileges are
-- separate things in Postgres, and service_role had never been given
-- either select or update on this table before now (only anon/authenticated
-- were, above, for normal RLS-gated client access). Without this, every
-- consolidate-steam-profiles call failed with
-- "permission denied for table profiles" (42501), confirmed live via the
-- Edge Function's own logs.
grant select, update on public.profiles to service_role;

-- =============================================================================
-- Public-launch hardening -- apply by hand in the SQL Editor, in one go.
-- (Run the "BEFORE" checks first; "AFTER" checks at the bottom confirm it.)
--
-- Why: before a public GitHub release, strangers can reach this project with
-- nothing but the publishable key in the source (that key is public by
-- design -- RLS and grants below are the actual protection). Four gaps:
--   1. profiles.recovery_secret_hash was readable by everyone (public select).
--      Not crackable in practice (bcrypt of a 160-bit random secret), but
--      there's no reason to publish it.
--   2. The Steam proxy's per-user daily cap is keyed by anonymous user, and
--      anyone can mint unlimited anonymous users -- so the cap alone doesn't
--      protect the one shared Steam key (Valve: 100k calls/day per key).
--   3. Any signed-in user could write unbounded arrays / arbitrary text into
--      their own row.
--   4. The RPC grants above only `revoke ... from public`. Supabase can also
--      grant EXECUTE directly to anon/authenticated (default privileges), which
--      "from public" does NOT remove -- so the "service_role only" functions
--      may have been callable by anyone. Revoked explicitly below.
--
-- BEFORE (optional, read-only) -- what's currently exposed:
--   select has_column_privilege('anon', 'public.profiles', 'recovery_secret_hash', 'select');
--   select has_function_privilege('anon', 'public.increment_steam_proxy_usage(uuid)', 'execute');
--   -- and rows that would violate the new constraints (these must be fixed or
--   -- deleted for VALIDATE to succeed later; NOT VALID below doesn't need it):
--   select arbg_user_id, steam_id from public.profiles
--   where arbg_user_id !~ '^GBLN-[2-9A-HJKMNP-Z]{5}$'
--      or (steam_id is not null and steam_id !~ '^[0-9]{17}$')
--      or cardinality(blueprints_owned) > 500
--      or cardinality(blueprints_wanted) > 500
--      or cardinality(blueprints_spare) > 500;
-- =============================================================================

-- 1. Column-level privileges on profiles. Postgres quirk (confirmed in
-- Supabase's column-level-security docs): a column grant does nothing while a
-- table-level grant exists, so revoke the table-level ones first. After this
-- clients must name columns -- `select *` errors (cloud/friends.py:
-- PROFILE_COLUMNS) -- and writes must use return=minimal (cloud/sync.py).
-- service_role keeps its own table-level select/update (consolidate function).
revoke select, insert, update on public.profiles from anon, authenticated;

grant select (id, arbg_user_id, steam_id, blueprints_owned, blueprints_wanted,
              blueprints_spare, updated_at, obsoleted_at)
  on public.profiles to anon, authenticated;

-- anon never writes (every write policy requires auth.uid()); authenticated
-- users may write only the columns the app actually sends. Excluded on
-- purpose: recovery_secret_hash (only set_recovery_secret may write it) and
-- obsoleted_at (only consolidate-steam-profiles, via service_role).
-- updated_at is set by the profiles_set_updated_at trigger, not the client.
-- id must be writable: PostgREST's upsert puts every payload column,
-- including id, in the ON CONFLICT DO UPDATE SET list (RLS's
-- `with check (auth.uid() = id)` still stops anyone changing it to another).
grant insert (id, arbg_user_id, steam_id, blueprints_owned, blueprints_wanted, blueprints_spare)
  on public.profiles to authenticated;
grant update (id, arbg_user_id, steam_id, blueprints_owned, blueprints_wanted, blueprints_spare)
  on public.profiles to authenticated;

-- 2. Global (all-users) daily cap on the Steam proxy -- enforced alongside the
-- per-user one in supabase/functions/_shared/steam_proxy_common.ts.
create table public.steam_proxy_global_usage (
  day date primary key default current_date,
  call_count integer not null default 0
);
alter table public.steam_proxy_global_usage enable row level security;

create or replace function public.increment_steam_proxy_global_usage()
returns integer
language sql
security definer
set search_path = public
as $$
  insert into public.steam_proxy_global_usage (day, call_count)
  values (current_date, 1)
  on conflict (day)
  do update set call_count = steam_proxy_global_usage.call_count + 1
  returning call_count;
$$;

-- 3. Bound what a user can store in their own row. NOT VALID: enforced for
-- every new/changed row immediately, without failing on any legacy test rows;
-- run `alter table public.profiles validate constraint <name>;` later once
-- the BEFORE query above returns nothing. 500 is generous headroom over the
-- current 83 blueprints.
alter table public.profiles
  add constraint profiles_arbg_user_id_format
    check (arbg_user_id ~ '^GBLN-[2-9A-HJKMNP-Z]{5}$') not valid,
  add constraint profiles_steam_id_format
    check (steam_id is null or steam_id ~ '^[0-9]{17}$') not valid,
  add constraint profiles_blueprint_arrays_bounded
    check (cardinality(blueprints_owned) <= 500
       and cardinality(blueprints_wanted) <= 500
       and cardinality(blueprints_spare) <= 500) not valid;

-- 4. Explicit revokes (see header, gap 4). service_role-only functions:
revoke all on function public.increment_steam_proxy_usage(uuid) from public, anon, authenticated;
revoke all on function public.increment_steam_proxy_global_usage() from public, anon, authenticated;
revoke all on function public.delete_stale_profiles() from public, anon, authenticated;
grant execute on function public.increment_steam_proxy_usage(uuid) to service_role;
grant execute on function public.increment_steam_proxy_global_usage() to service_role;
-- authenticated-only functions (both no-op without auth.uid(), so anon access
-- was dead weight, not a leak -- revoked anyway for tidiness):
revoke all on function public.set_recovery_secret(text, text) from public, anon;
revoke all on function public.reclaim_profile(text, text) from public, anon;

-- AFTER (read-only) -- every line should return false:
--   select has_column_privilege('anon', 'public.profiles', 'recovery_secret_hash', 'select');
--   select has_column_privilege('authenticated', 'public.profiles', 'recovery_secret_hash', 'select');
--   select has_column_privilege('authenticated', 'public.profiles', 'recovery_secret_hash', 'update');
--   select has_column_privilege('authenticated', 'public.profiles', 'obsoleted_at', 'update');
--   select has_function_privilege('anon', 'public.increment_steam_proxy_usage(uuid)', 'execute');
--   select has_function_privilege('authenticated', 'public.increment_steam_proxy_global_usage()', 'execute');
-- and these true:
--   select has_column_privilege('anon', 'public.profiles', 'steam_id', 'select');
--   select has_column_privilege('authenticated', 'public.profiles', 'blueprints_owned', 'update');
--
-- ROLLBACK (restores the pre-hardening grants exactly):
--   grant select, insert, update on public.profiles to anon, authenticated;
--   alter table public.profiles drop constraint profiles_arbg_user_id_format,
--     drop constraint profiles_steam_id_format, drop constraint profiles_blueprint_arrays_bounded;
