from supabase import Client


def fetch_friend_profiles(client: Client, arbg_user_ids: list[str]) -> list[dict]:
    """One batched query for every friend's profiles row. RLS grants select
    to the anon role with a `using (true)` policy (see supabase/schema.sql),
    so this doesn't strictly need an authenticated session -- callers that
    already have one (e.g. mid-sync) just reuse it at no extra cost."""
    if not arbg_user_ids:
        return []
    result = client.table("profiles").select("*").in_("arbg_user_id", arbg_user_ids).execute()
    return result.data
