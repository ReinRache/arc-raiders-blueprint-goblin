// Shared helpers for the two Steam Web API proxy functions
// (steam-player-summaries, steam-friend-list). Both exist so no end user
// ever needs their own Steam Web API key -- Valve requires a phone number
// and a non-"limited" account to generate one, which blocked a real user of
// this app outright. One key (this project owner's own, already working),
// held here as a secret, resolves names/friends for everyone -- a Web API
// key authenticates the calling application, not which Steam account's
// data it's allowed to fetch.
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

export const STEAM_API_BASE = "https://api.steampowered.com";

// Generous relative to real usage (a handful of calls per user per sync/
// discovery click) -- this exists to stop a runaway bug or deliberate abuse
// from draining the shared key's quota or getting it flagged by Valve, not
// to meter normal use.
const DAILY_CALL_CAP = 200;

export function jsonError(error: string, status: number): Response {
  return new Response(JSON.stringify({ error }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function jsonOk(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// Resolves the caller's auth.uid() from the request's own bearer token,
// using the anon key (never the service role) -- this client can only ever
// find out who the caller is, not read/write anything privileged.
export async function resolveCallerId(req: Request): Promise<string | null> {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return null;
  const anonClient = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } },
  );
  const { data, error } = await anonClient.auth.getUser();
  if (error || !data.user) return null;
  return data.user.id;
}

// SUPABASE_SERVICE_ROLE_KEY is auto-injected into every Edge Function by
// Supabase -- never a client-supplied value, never logged. Bypasses RLS by
// design, which is exactly why steam_proxy_usage has no anon/authenticated
// grants at all: only this key can ever touch it.
function serviceRoleClient(): SupabaseClient {
  return createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
}

// Atomically increments today's row for this user (see
// increment_steam_proxy_usage in supabase/schema.sql -- a single
// INSERT ... ON CONFLICT DO UPDATE, not a separate read-then-write, so
// concurrent calls from the same user can't under-count each other) and
// reports whether they were already at/over the cap *before* this call.
export async function checkAndIncrementUsage(userId: string): Promise<boolean> {
  const client = serviceRoleClient();
  const { data, error } = await client.rpc("increment_steam_proxy_usage", {
    p_user_id: userId,
  });
  if (error) {
    // Fail closed on our own infra trouble -- better to reject a request
    // than silently skip rate limiting because the counter call broke.
    return false;
  }
  return (data as number) <= DAILY_CALL_CAP;
}

export function getSteamApiKey(): string {
  const key = Deno.env.get("STEAM_WEB_API_KEY");
  if (!key) {
    throw new Error("STEAM_WEB_API_KEY is not configured");
  }
  return key;
}
