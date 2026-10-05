// Proxies GetPlayerSummaries/v2/ -- see _shared/steam_proxy_common.ts for
// why this exists (no per-user Steam Web API key required). Mirrors the
// Python steam.web_api.get_player_summaries() this replaces: same batching
// cap, same {steamid: personaname} response shape, silently skips any
// player entry missing either field.
import {
  checkAndIncrementUsage,
  getSteamApiKey,
  jsonError,
  jsonOk,
  resolveCallerId,
  STEAM_API_BASE,
  STEAM_ID_PATTERN,
} from "../_shared/steam_proxy_common.ts";

const MAX_STEAMIDS_PER_CALL = 100;

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

  let body: { steam_ids?: unknown };
  try {
    body = await req.json();
  } catch {
    return jsonError("invalid_body", 400);
  }

  const steamIds = Array.isArray(body.steam_ids)
    ? body.steam_ids.filter((id): id is string => typeof id === "string" && STEAM_ID_PATTERN.test(id))
    : [];
  if (steamIds.length === 0) {
    return jsonOk({});
  }
  // Truncate rather than loop over multiple upstream Steam calls in one
  // invocation -- a single client call fanning out into many Steam requests
  // is exactly the amplification the rate limit above is trying to avoid.
  // In practice a player's own friend list rarely exceeds 100 anyway.
  const batch = steamIds.slice(0, MAX_STEAMIDS_PER_CALL);

  const url = new URL(`${STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v2/`);
  url.searchParams.set("key", getSteamApiKey());
  url.searchParams.set("steamids", batch.join(","));

  const steamResponse = await fetch(url);
  if (!steamResponse.ok) {
    return jsonError("steam_request_failed", 502);
  }
  const data = await steamResponse.json();
  const players = data?.response?.players ?? [];

  const names: Record<string, string> = {};
  for (const player of players) {
    if (typeof player?.steamid === "string" && typeof player?.personaname === "string") {
      names[player.steamid] = player.personaname;
    }
  }
  return jsonOk(names);
});
