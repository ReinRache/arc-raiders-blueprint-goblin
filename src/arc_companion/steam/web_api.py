"""Steam Web API calls for friend-related data -- distinct from
openid_auth.py, which only handles sign-in. These use the standard
api.steampowered.com host with a personal (BYOK) user Web API key, not the
partner.steam-api.com domain -- confirmed via Valve's docs during planning
that this is the correct, only-available mechanism for a fan-made tool (see
Stage A's original research into the same question for OpenID).
"""

import requests

STEAM_API_BASE = "https://api.steampowered.com"
_REQUEST_TIMEOUT_SECONDS = 10
# GetPlayerSummaries accepts at most 100 steamids per call.
_MAX_STEAMIDS_PER_SUMMARY_CALL = 100


class SteamFriendsListPrivateError(Exception):
    """Raised when GetFriendList returns HTTP 401 -- confirmed via Valve's
    docs that this specifically means the target account's "Friends List"
    Steam privacy setting is not public, not a bad key or other failure."""


def get_player_summaries(api_key: str, steam_ids: list[str]) -> dict[str, str]:
    """Returns {steamid: personaname} for however many of the requested IDs
    Steam has public data for. Batches into groups of 100 (the API's own
    limit) -- in practice a single player's friend list rarely exceeds that,
    but this stays correct either way."""
    names: dict[str, str] = {}
    for start in range(0, len(steam_ids), _MAX_STEAMIDS_PER_SUMMARY_CALL):
        batch = steam_ids[start : start + _MAX_STEAMIDS_PER_SUMMARY_CALL]
        response = requests.get(
            f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": api_key, "steamids": ",".join(batch)},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        for player in response.json().get("response", {}).get("players", []):
            if "steamid" in player and "personaname" in player:
                names[player["steamid"]] = player["personaname"]
    return names


def get_friend_list(api_key: str, steam_id: str) -> list[str]:
    """Returns the SteamID64s of steam_id's friends. Raises
    SteamFriendsListPrivateError if that account's friends list isn't
    public -- the caller should show that as an actionable message, not a
    generic failure."""
    response = requests.get(
        f"{STEAM_API_BASE}/ISteamUser/GetFriendList/v1/",
        params={"key": api_key, "steamid": steam_id, "relationship": "friend"},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code == 401:
        raise SteamFriendsListPrivateError(
            "This Steam account's friends list is not set to public."
        )
    response.raise_for_status()
    friends = response.json().get("friendslist", {}).get("friends", [])
    return [friend["steamid"] for friend in friends if "steamid" in friend]
