from supabase import Client

from arc_companion.storage.base import UserState
from arc_companion.storage.supabase_session import SupabaseSession, SupabaseSessionStore


def ensure_session(client: Client, session_store: SupabaseSessionStore) -> str:
    """Restores a saved anonymous-auth session, or creates a new one on first
    use (or if the saved session can no longer be restored, e.g. a revoked
    refresh token -- treated the same as a fresh install, per the accepted
    "lost session = orphaned cloud row" limitation rather than surfacing an
    error the user can't act on). Returns the resolved auth.uid().

    Only ever called lazily from an explicit user action (Sync, Wipe) --
    never on app startup -- so launching the app stays offline-friendly.
    """
    saved = session_store.load()
    response = None
    if saved.access_token and saved.refresh_token:
        try:
            response = client.auth.set_session(saved.access_token, saved.refresh_token)
        except Exception:
            response = None
    if response is None or response.session is None:
        response = client.auth.sign_in_anonymously()

    session_store.save(
        SupabaseSession(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
        )
    )
    return response.session.user.id


def push_profile(client: Client, user_id: str, user_state: UserState) -> None:
    client.table("profiles").upsert(
        {
            "id": user_id,
            "arbg_user_id": user_state.arbg_user_id,
            "steam_id": user_state.steam_id,
            "blueprints_owned": user_state.blueprints_owned,
            "blueprints_wanted": user_state.blueprints_wanted,
            "blueprints_spare": user_state.blueprints_spare,
        }
    ).execute()


def wipe_cloud_data(client: Client, user_id: str) -> None:
    client.table("profiles").update(
        {"blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": []}
    ).eq("id", user_id).execute()
