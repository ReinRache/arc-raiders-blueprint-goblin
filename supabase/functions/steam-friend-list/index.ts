// Proxies GetFriendList/v1/ -- see _shared/steam_proxy_common.ts for why
// this exists (no per-user Steam Web API key required). Mirrors the Python
// steam.web_api.get_friend_list() this replaces, including translating
// Steam's HTTP 401 (target account's friends list isn't public) into a
// clean 403 + {"error": "friends_list_private"} the client can branch on by
// status code instead of string-matching.
import {
  checkAndIncrementUsage,
  getSteamApiKey,
  jsonError,
  jsonOk,
  resolveCallerId,
  STEAM_API_BASE,
  STEAM_ID_PATTERN,
} from "../_shared/steam_proxy_common.ts";

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return jsonError("method_not_allowed", 405);
  }

  const userId = await resolveCallerId(req);
  if (!userId) {
    return jsonError("unauthorized", 401);
  }

  const withinCap = await checkAndIncrementUsage(userId);
  if (!withinCap) {
    return jsonError("rate_limited", 429);
  }

  let body: { steam_id?: unknown };
  try {
    body = await req.json();
  } catch {
    return jsonError("invalid_body", 400);
  }

  if (typeof body.steam_id !== "string" || !STEAM_ID_PATTERN.test(body.steam_id)) {
    return jsonError("invalid_body", 400);
  }

  const url = new URL(`${STEAM_API_BASE}/ISteamUser/GetFriendList/v1/`);
  url.searchParams.set("key", getSteamApiKey());
  url.searchParams.set("steamid", body.steam_id);
  url.searchParams.set("relationship", "friend");

  const steamResponse = await fetch(url);
  if (steamResponse.status === 401) {
    return jsonError("friends_list_private", 403);
  }
  if (!steamResponse.ok) {
    return jsonError("steam_request_failed", 502);
  }
  const data = await steamResponse.json();
  const friends = data?.friendslist?.friends ?? [];
  const steamIds = friends
    .map((friend: { steamid?: unknown }) => friend?.steamid)
    .filter((id: unknown): id is string => typeof id === "string");

  return jsonOk({ steam_ids: steamIds });
});
