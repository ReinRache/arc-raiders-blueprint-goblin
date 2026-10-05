from types import SimpleNamespace

import pytest
from postgrest import ReturnMethod
from postgrest.exceptions import APIError

from arc_companion.cloud.sync import (
    RecoveryOutcome,
    _is_arbg_id_conflict,
    ensure_session,
    push_profile,
    push_profile_with_recovery,
    wipe_cloud_data,
)
from arc_companion.storage.base import UserState
from arc_companion.storage.supabase_session import SupabaseSession, SupabaseSessionStore


def _arbg_id_conflict_error() -> APIError:
    return APIError(
        {
            "message": 'duplicate key value violates unique constraint "profiles_arbg_user_id_key"',
            "code": "23505",
            "hint": None,
            "details": None,
        }
    )


def _auth_response(access_token: str, refresh_token: str, user_id: str) -> SimpleNamespace:
    user = SimpleNamespace(id=user_id)
    session = SimpleNamespace(access_token=access_token, refresh_token=refresh_token, user=user)
    return SimpleNamespace(session=session, user=user)


class FakeAuth:
    def __init__(self, sign_in_response=None, set_session_response=None, set_session_error=None):
        self._sign_in_response = sign_in_response
        self._set_session_response = set_session_response
        self._set_session_error = set_session_error
        self.sign_in_calls = 0
        self.set_session_calls = []

    def sign_in_anonymously(self):
        self.sign_in_calls += 1
        return self._sign_in_response

    def set_session(self, access_token, refresh_token):
        self.set_session_calls.append((access_token, refresh_token))
        if self._set_session_error is not None:
            raise self._set_session_error
        return self._set_session_response


class FakeTableQuery:
    def __init__(self, table: str, recorder: list, client: "FakeClient"):
        self.table = table
        self.recorder = recorder
        self._client = client
        self._is_upsert = False

    def upsert(self, payload, returning=None):
        self.recorder.append(("upsert", self.table, payload))
        self._client.returning_methods.append(returning)
        self._is_upsert = True
        return self

    def update(self, payload, returning=None):
        self.recorder.append(("update", self.table, payload))
        self._client.returning_methods.append(returning)
        return self

    def eq(self, column, value):
        self.recorder.append(("eq", column, value))
        return self

    def execute(self):
        # Consumed in order -- lets a test simulate "first upsert raises
        # (e.g. the arbg_user_id collision), retried upsert succeeds" by
        # passing a single-item list, with no extra bookkeeping needed:
        # once the queue is empty, every further call just succeeds.
        if self._is_upsert and self._client.upsert_side_effects:
            effect = self._client.upsert_side_effects.pop(0)
            if effect is not None:
                raise effect
        return SimpleNamespace(data=[])


class FakeRPCQuery:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return SimpleNamespace(data=self._response)


class FakeClient:
    def __init__(self, auth: FakeAuth, upsert_side_effects=None, rpc_responses=None):
        self.auth = auth
        self.calls: list = []
        self.rpc_calls: list = []
        self.returning_methods: list = []
        self.upsert_side_effects: list = list(upsert_side_effects) if upsert_side_effects else []
        self._rpc_responses = rpc_responses or {}

    def table(self, name: str) -> FakeTableQuery:
        return FakeTableQuery(name, self.calls, self)

    def rpc(self, fn: str, params: dict) -> FakeRPCQuery:
        self.rpc_calls.append((fn, params))
        return FakeRPCQuery(self._rpc_responses.get(fn))


def test_ensure_session_signs_in_anonymously_when_no_saved_session(tmp_path):
    store = SupabaseSessionStore(path=tmp_path / "supabase_session.json")
    response = _auth_response("new-access", "new-refresh", "user-1")
    client = FakeClient(FakeAuth(sign_in_response=response))

    user_id = ensure_session(client, store)

    assert user_id == "user-1"
    assert client.auth.sign_in_calls == 1
    assert client.auth.set_session_calls == []
    saved = store.load()
    assert saved.access_token == "new-access"
    assert saved.refresh_token == "new-refresh"


def test_ensure_session_restores_saved_session(tmp_path):
    store = SupabaseSessionStore(path=tmp_path / "supabase_session.json")
    store.save(SupabaseSession(access_token="old-access", refresh_token="old-refresh"))
    response = _auth_response("refreshed-access", "refreshed-refresh", "user-2")
    client = FakeClient(FakeAuth(set_session_response=response))

    user_id = ensure_session(client, store)

    assert user_id == "user-2"
    assert client.auth.sign_in_calls == 0
    assert client.auth.set_session_calls == [("old-access", "old-refresh")]
    saved = store.load()
    assert saved.access_token == "refreshed-access"
    assert saved.refresh_token == "refreshed-refresh"


def test_ensure_session_falls_back_to_sign_in_if_restore_fails(tmp_path):
    store = SupabaseSessionStore(path=tmp_path / "supabase_session.json")
    store.save(SupabaseSession(access_token="stale-access", refresh_token="revoked-refresh"))
    fresh_response = _auth_response("fresh-access", "fresh-refresh", "user-3")
    client = FakeClient(
        FakeAuth(sign_in_response=fresh_response, set_session_error=Exception("revoked"))
    )

    user_id = ensure_session(client, store)

    assert user_id == "user-3"
    assert client.auth.set_session_calls == [("stale-access", "revoked-refresh")]
    assert client.auth.sign_in_calls == 1
    saved = store.load()
    assert saved.access_token == "fresh-access"


def test_push_profile_upserts_expected_payload():
    client = FakeClient(FakeAuth())
    user_state = UserState(
        arbg_user_id="GBLN-23456",
        steam_id="76561198000000000",
        blueprints_owned=[1, 2, 3],
        blueprints_wanted=[4],
        blueprints_spare=[3],
    )

    push_profile(client, "user-123", user_state)

    assert client.calls == [
        (
            "upsert",
            "profiles",
            {
                "id": "user-123",
                "arbg_user_id": "GBLN-23456",
                "steam_id": "76561198000000000",
                "blueprints_owned": [1, 2, 3],
                "blueprints_wanted": [4],
                "blueprints_spare": [3],
            },
        )
    ]


def test_wipe_cloud_data_clears_arrays_for_own_row():
    client = FakeClient(FakeAuth())

    wipe_cloud_data(client, "user-123")

    assert client.calls == [
        (
            "update",
            "profiles",
            {"blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": []},
        ),
        ("eq", "id", "user-123"),
    ]


# ---- _is_arbg_id_conflict ---------------------------------------------------


def test_is_arbg_id_conflict_true_for_the_real_shape():
    assert _is_arbg_id_conflict(_arbg_id_conflict_error())


def test_is_arbg_id_conflict_false_for_right_code_wrong_constraint():
    exc = APIError(
        {
            "message": 'duplicate key value violates unique constraint "some_other_key"',
            "code": "23505",
            "hint": None,
            "details": None,
        }
    )
    assert not _is_arbg_id_conflict(exc)


def test_is_arbg_id_conflict_false_for_wrong_code_right_message():
    exc = APIError(
        {
            "message": 'duplicate key value violates unique constraint "profiles_arbg_user_id_key"',
            "code": "23000",
            "hint": None,
            "details": None,
        }
    )
    assert not _is_arbg_id_conflict(exc)


def test_is_arbg_id_conflict_false_for_non_api_error():
    assert not _is_arbg_id_conflict(ConnectionError("boom"))


# ---- push_profile_with_recovery ---------------------------------------------


def _user_state(**overrides) -> UserState:
    defaults = dict(arbg_user_id="GBLN-23456", recovery_secret="s3cr3t" * 5)
    defaults.update(overrides)
    return UserState(**defaults)


def test_push_profile_with_recovery_calls_set_recovery_secret_after_normal_push():
    client = FakeClient(FakeAuth())
    user_state = _user_state()

    outcome = push_profile_with_recovery(client, "user-1", user_state)

    assert outcome == RecoveryOutcome()
    assert client.rpc_calls == [
        ("set_recovery_secret", {"p_arbg_user_id": "GBLN-23456", "p_secret": user_state.recovery_secret})
    ]


def test_push_profile_with_recovery_skips_set_recovery_secret_when_none_locally():
    client = FakeClient(FakeAuth())
    user_state = _user_state(recovery_secret=None)

    outcome = push_profile_with_recovery(client, "user-1", user_state)

    assert outcome == RecoveryOutcome()
    assert client.rpc_calls == []


def test_push_profile_with_recovery_reclaims_on_conflict_when_secret_matches():
    client = FakeClient(
        FakeAuth(),
        upsert_side_effects=[_arbg_id_conflict_error()],
        rpc_responses={"reclaim_profile": True},
    )
    user_state = _user_state()

    outcome = push_profile_with_recovery(client, "user-1", user_state)

    assert outcome == RecoveryOutcome(reclaimed=True)
    upsert_calls = [c for c in client.calls if c[0] == "upsert"]
    assert len(upsert_calls) == 2  # the failed attempt, then the retry after reclaiming
    assert upsert_calls[0] == upsert_calls[1]  # same payload both times -- same identity throughout
    assert client.rpc_calls == [
        ("reclaim_profile", {"p_arbg_user_id": "GBLN-23456", "p_secret": user_state.recovery_secret}),
        ("set_recovery_secret", {"p_arbg_user_id": "GBLN-23456", "p_secret": user_state.recovery_secret}),
    ]


def test_push_profile_with_recovery_regenerates_identity_when_reclaim_returns_false():
    client = FakeClient(
        FakeAuth(),
        upsert_side_effects=[_arbg_id_conflict_error()],
        rpc_responses={"reclaim_profile": False},
    )
    user_state = _user_state()

    outcome = push_profile_with_recovery(client, "user-1", user_state)

    assert outcome.regenerated is True
    assert outcome.reclaimed is False
    assert outcome.new_arbg_user_id is not None
    assert outcome.new_arbg_user_id != user_state.arbg_user_id
    assert outcome.new_recovery_secret is not None
    assert outcome.new_recovery_secret != user_state.recovery_secret

    upsert_calls = [c for c in client.calls if c[0] == "upsert"]
    assert len(upsert_calls) == 2
    assert upsert_calls[1][2]["arbg_user_id"] == outcome.new_arbg_user_id  # retried under the new identity

    reclaim_call = next(c for c in client.rpc_calls if c[0] == "reclaim_profile")
    assert reclaim_call == ("reclaim_profile", {"p_arbg_user_id": "GBLN-23456", "p_secret": user_state.recovery_secret})
    set_secret_call = next(c for c in client.rpc_calls if c[0] == "set_recovery_secret")
    assert set_secret_call == (
        "set_recovery_secret",
        {"p_arbg_user_id": outcome.new_arbg_user_id, "p_secret": outcome.new_recovery_secret},
    )


def test_push_profile_with_recovery_regenerates_when_no_local_secret_at_all():
    client = FakeClient(FakeAuth(), upsert_side_effects=[_arbg_id_conflict_error()])
    user_state = _user_state(recovery_secret=None)

    outcome = push_profile_with_recovery(client, "user-1", user_state)

    assert outcome.regenerated is True
    # Nothing to try reclaiming with -- reclaim_profile should never be called.
    assert all(call[0] != "reclaim_profile" for call in client.rpc_calls)


def test_push_profile_with_recovery_reraises_unrelated_unique_violations():
    other_violation = APIError(
        {
            "message": 'duplicate key value violates unique constraint "some_other_key"',
            "code": "23505",
            "hint": None,
            "details": None,
        }
    )
    client = FakeClient(FakeAuth(), upsert_side_effects=[other_violation])
    user_state = _user_state()

    with pytest.raises(APIError):
        push_profile_with_recovery(client, "user-1", user_state)
    assert client.rpc_calls == []


def test_push_profile_with_recovery_reraises_non_conflict_errors_unchanged():
    client = FakeClient(FakeAuth(), upsert_side_effects=[ConnectionError("boom")])
    user_state = _user_state()

    with pytest.raises(ConnectionError):
        push_profile_with_recovery(client, "user-1", user_state)
    assert client.rpc_calls == []


def test_profile_writes_use_returning_minimal():
    # The default (representation) is RETURNING *, which includes
    # recovery_secret_hash -- a column clients have no SELECT privilege on.
    client = FakeClient(FakeAuth())
    push_profile(client, "user-1", UserState(arbg_user_id="GBLN-23456"))
    wipe_cloud_data(client, "user-1")
    assert client.returning_methods == [ReturnMethod.minimal, ReturnMethod.minimal]
