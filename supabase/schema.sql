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
