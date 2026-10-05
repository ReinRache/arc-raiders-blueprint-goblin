from supabase import Client

# Explicit, never "*": clients have no SELECT privilege on
# profiles.recovery_secret_hash (supabase/schema.sql, "Public-launch
# hardening"), and PostgREST rejects "*" outright when any column is
# ungranted. Everything here is data a friend lookup legitimately needs.
PROFILE_COLUMNS = (
    "id,arbg_user_id,steam_id,blueprints_owned,blueprints_wanted,"
    "blueprints_spare,updated_at,obsoleted_at"
)


def fetch_friend_profiles(client: Client, arbg_user_ids: list[str]) -> list[dict]:
    """One batched query for every friend's profiles row. RLS grants select
    to the anon role with a `using (true)` policy (see supabase/schema.sql),
    so this doesn't strictly need an authenticated session -- callers that
    already have one (e.g. mid-sync) just reuse it at no extra cost.

    Excludes obsoleted rows (see supabase/functions/consolidate-steam-
    profiles) -- a superseded duplicate profile shouldn't show up as a
    legitimate friend, same "just stops appearing next refresh" treatment
    already used for stale-cleanup deletions."""
    if not arbg_user_ids:
        return []
    result = (
        client.table("profiles")
        .select(PROFILE_COLUMNS)
        .in_("arbg_user_id", arbg_user_ids)
        .is_("obsoleted_at", None)
        .execute()
    )
    return result.data


def fetch_profiles_by_steam_ids(client: Client, steam_ids: list[str]) -> list[dict]:
    """One batched query matching real-life Steam friends (SteamID64s from
    GetFriendList) against profiles rows -- the actual auto-discovery match:
    which of my Steam friends are also on this app with Steam linked. Same
    anon-readable RLS as fetch_friend_profiles, no auth required.

    Excludes obsoleted rows, same reasoning as fetch_friend_profiles above."""
    if not steam_ids:
        return []
    result = (
        client.table("profiles")
        .select(PROFILE_COLUMNS)
        .in_("steam_id", steam_ids)
        .is_("obsoleted_at", None)
        .execute()
    )
    return result.data
