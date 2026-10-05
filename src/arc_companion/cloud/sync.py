import dataclasses

from postgrest import ReturnMethod
from postgrest.exceptions import APIError
from supabase import Client

from arc_companion.identity import generate_arbg_id, generate_recovery_secret
from arc_companion.storage.base import UserState
from arc_companion.storage.supabase_session import SupabaseSession, SupabaseSessionStore

# The exact unique constraint name Postgres uses for `arbg_user_id text not
# null unique` on `profiles` (auto-named <table>_<column>_key) -- checked
# alongside the SQLSTATE below so an unrelated future unique constraint on
# this table never gets misclassified into the reclaim/regenerate path.
_ARBG_USER_ID_UNIQUE_CONSTRAINT = "profiles_arbg_user_id_key"
_UNIQUE_VIOLATION_SQLSTATE = "23505"


def ensure_session(client: Client, session_store: SupabaseSessionStore) -> str:
    """Restores a saved anonymous-auth session, or creates a new one on first
    use (or if the saved session can no longer be restored, e.g. a revoked
    refresh token). Returns the resolved auth.uid().

    A fresh auth.uid() minted here after a lost session is exactly what
    orphans the old profiles row under the old, now-unreachable auth.uid()
    -- see push_profile_with_recovery below for how that gets resolved on
    the next push, instead of just failing.

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
        },
        # minimal: nothing to read back, and the default ("representation")
        # asks for RETURNING *, which includes recovery_secret_hash -- a
        # column clients have no SELECT privilege on (supabase/schema.sql,
        # "Public-launch hardening"), so the write would be rejected.
        returning=ReturnMethod.minimal,
    ).execute()


def _is_arbg_id_conflict(exc: Exception) -> bool:
    """True only for the exact unique_violation push_profile_with_recovery
    knows how to handle -- checks both the SQLSTATE and the constraint name,
    not code alone, so an unrelated future unique constraint on profiles
    isn't misclassified into the reclaim/regenerate path."""
    return (
        isinstance(exc, APIError)
        and exc.code == _UNIQUE_VIOLATION_SQLSTATE
        and exc.message is not None
        and _ARBG_USER_ID_UNIQUE_CONSTRAINT in exc.message
    )


def _set_recovery_secret(client: Client, arbg_user_id: str, recovery_secret: str) -> None:
    client.rpc(
        "set_recovery_secret", {"p_arbg_user_id": arbg_user_id, "p_secret": recovery_secret}
    ).execute()


def _reclaim_profile(client: Client, arbg_user_id: str, recovery_secret: str) -> bool:
    response = client.rpc(
        "reclaim_profile", {"p_arbg_user_id": arbg_user_id, "p_secret": recovery_secret}
    ).execute()
    return bool(response.data)


@dataclasses.dataclass
class RecoveryOutcome:
    reclaimed: bool = False
    regenerated: bool = False
    new_arbg_user_id: str | None = None
    new_recovery_secret: str | None = None


def push_profile_with_recovery(client: Client, user_id: str, user_state: UserState) -> RecoveryOutcome:
    """Same effect as push_profile, plus automatic recovery from the
    orphaned-row unique-violation case: a lost supabase_session.json + a
    surviving config.json mints a fresh auth.uid() (see ensure_session
    above) whose first push collides with the old row's now-unreachable
    arbg_user_id.

    Tries, in order:
    1. The normal push. If it succeeds outright, reaffirms this install's
       recovery secret server-side (set_recovery_secret is a safe no-op
       once already set -- see supabase/schema.sql) so a *future* lost
       session has something to reclaim against.
    2. On exactly that conflict, if a local recovery_secret exists, tries
       reclaim_profile() to re-parent the old row onto the new auth.uid()
       and retries the push.
    3. If reclaim isn't possible (no local secret, wrong secret, or a
       pre-migration row that never had one set), mints a brand-new
       arbg_user_id + recovery_secret and pushes under that identity
       instead -- always safe, since a never-before-used arbg_user_id can't
       collide with anyone. Callers must surface this to the user (their
       Goblin ID changed) via the returned RecoveryOutcome, not swallow it.

    Any other exception, including a failure of the retried push itself,
    propagates unchanged.
    """
    try:
        push_profile(client, user_id, user_state)
    except APIError as exc:
        if not _is_arbg_id_conflict(exc):
            raise
        if user_state.recovery_secret and _reclaim_profile(
            client, user_state.arbg_user_id, user_state.recovery_secret
        ):
            push_profile(client, user_id, user_state)
            _set_recovery_secret(client, user_state.arbg_user_id, user_state.recovery_secret)
            return RecoveryOutcome(reclaimed=True)

        new_arbg_user_id = generate_arbg_id()
        new_recovery_secret = generate_recovery_secret()
        regenerated_state = dataclasses.replace(
            user_state, arbg_user_id=new_arbg_user_id, recovery_secret=new_recovery_secret
        )
        push_profile(client, user_id, regenerated_state)
        _set_recovery_secret(client, new_arbg_user_id, new_recovery_secret)
        return RecoveryOutcome(
            regenerated=True,
            new_arbg_user_id=new_arbg_user_id,
            new_recovery_secret=new_recovery_secret,
        )
    else:
        if user_state.recovery_secret:
            _set_recovery_secret(client, user_state.arbg_user_id, user_state.recovery_secret)
        return RecoveryOutcome()


def wipe_cloud_data(client: Client, user_id: str) -> None:
    client.table("profiles").update(
        {"blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": []},
        returning=ReturnMethod.minimal,  # see push_profile
    ).eq("id", user_id).execute()
