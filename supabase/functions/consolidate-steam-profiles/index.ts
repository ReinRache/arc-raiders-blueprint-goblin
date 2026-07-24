// Marks every OTHER profiles row sharing a verified SteamID64 as obsolete,
// leaving only the caller's own row active for that Steam account. Exists
// because repeated test installs linking the same real Steam account each
// mint their own Goblin ID, leaving duplicate rows cluttering Find Steam
// Friends / the friend-overlay grid.
//
// Deliberately NOT gated on a client-supplied steam_id -- SteamID64s are
// usually publicly discoverable (a Steam profile URL contains one), so
// trusting a claimed value here would let anyone obsolete any other active
// user's row just by knowing it. Instead this independently re-verifies a
// real Steam OpenID 2.0 assertion server-side (re-running the exact
// check_authentication call src/arc_companion/steam/openid_auth.py's
// verify_openid_response() already does client-side) before touching
// anything -- the steam_id acted on always comes from that verification,
// never from the request body.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { jsonError, jsonOk, resolveCallerId } from "../_shared/steam_proxy_common.ts";

const STEAM_OPENID_URL = "https://steamcommunity.com/openid/login";

// Direct translation of openid_auth.py:verify_openid_response() -- same
// request shape (form-encoded POST, openid.mode overwritten to
// "check_authentication"), same plain substring check on the response body
// (not full key-value parsing), same claimed_id parsing. Returns null on
// any failure: network error, non-2xx, invalid assertion, malformed
// claimed_id.
async function verifySteamOpenId(params: Record<string, string>): Promise<string | null> {
  const verifyParams = new URLSearchParams(params);
  verifyParams.set("openid.mode", "check_authentication");

  let response: Response;
  try {
    response = await fetch(STEAM_OPENID_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: verifyParams.toString(),
    });
  } catch {
    return null;
  }
  if (!response.ok) return null;

  const text = await response.text();
  if (!text.includes("is_valid:true")) return null;

  const claimedId = params["openid.claimed_id"] ?? "";
  const steamId = claimedId.split("/").pop() ?? "";
  return /^\d+$/.test(steamId) ? steamId : null;
}

// A local copy of _shared/steam_proxy_common.ts's serviceRoleClient()
// rather than exporting/importing that one -- small, deliberate
// duplication to avoid touching already-deployed shared code used by the
// two Steam proxy functions for an unrelated feature.
function serviceRoleClient() {
  return createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return jsonError("method_not_allowed", 405);
  }

  const callerId = await resolveCallerId(req);
  if (!callerId) {
    return jsonError("unauthorized", 401);
  }

  let body: { openid_params?: unknown };
  try {
    body = await req.json();
  } catch {
    return jsonError("invalid_body", 400);
  }

  const openidParams = body.openid_params;
  if (typeof openidParams !== "object" || openidParams === null || Array.isArray(openidParams)) {
    return jsonError("invalid_body", 400);
  }

  const steamId = await verifySteamOpenId(openidParams as Record<string, string>);
  if (!steamId) {
    return jsonError("openid_verification_failed", 401);
  }

  const client = serviceRoleClient();
  const { data, error } = await client
    .from("profiles")
    .update({ obsoleted_at: new Date().toISOString() })
    .eq("steam_id", steamId)
    .neq("id", callerId)
    .is("obsoleted_at", null)
    .select("id");

  if (error) {
    console.error("consolidate-steam-profiles update failed:", JSON.stringify(error));
    return jsonError("database_error", 500);
  }

  return jsonOk({ obsoleted_count: data?.length ?? 0 });
});
