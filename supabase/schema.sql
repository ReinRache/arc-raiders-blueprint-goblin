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
