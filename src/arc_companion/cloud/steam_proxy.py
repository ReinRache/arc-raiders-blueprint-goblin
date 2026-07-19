from supabase import Client
from supabase_functions.errors import FunctionsHttpError


class SteamFriendsListPrivateError(Exception):
    """Raised when the target account's "Friends List" Steam privacy setting
    isn't public -- moved here from the now-deleted steam/web_api.py, same
    meaning, just detected from the proxy's 403 instead of Steam's own 401
    directly."""


class SteamProxyRateLimitedError(Exception):
    """Raised when the caller has hit the shared key's per-user daily cap
    (see supabase/functions/_shared/steam_proxy_common.ts) -- expected to be
    rare in normal use, but real enough to show as an actionable message
    rather than the generic failure case."""


def get_player_summaries(client: Client, steam_ids: list[str]) -> dict[str, str]:
    """Returns {steamid: personaname} via the steam-player-summaries Edge
    Function -- no per-user Steam Web API key needed. Requires an
    authenticated Supabase session (ensure_session(...) must already have
    been called on this client)."""
    if not steam_ids:
        return {}
    try:
        return client.functions.invoke(
            "steam-player-summaries",
            {"body": {"steam_ids": steam_ids}, "responseType": "json"},
        )
    except FunctionsHttpError as exc:
        if exc.status == 429:
            raise SteamProxyRateLimitedError("Too many requests — try again later.") from exc
        raise


def get_friend_list(client: Client, steam_id: str) -> list[str]:
    """Returns the SteamID64s of steam_id's friends via the steam-friend-list
    Edge Function -- no per-user Steam Web API key needed. Requires an
    authenticated Supabase session (ensure_session(...) must already have
    been called on this client)."""
    try:
        response = client.functions.invoke(
            "steam-friend-list",
            {"body": {"steam_id": steam_id}, "responseType": "json"},
        )
    except FunctionsHttpError as exc:
        if exc.status == 403 and exc.message == "friends_list_private":
            raise SteamFriendsListPrivateError(
                "This Steam account's friends list is not set to public."
            ) from exc
        if exc.status == 429:
            raise SteamProxyRateLimitedError("Too many requests — try again later.") from exc
        raise
    return response.get("steam_ids", [])
