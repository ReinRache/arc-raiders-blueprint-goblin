from types import SimpleNamespace

from arc_companion.cloud.sync import ensure_session, push_profile, wipe_cloud_data
from arc_companion.storage.base import UserState
from arc_companion.storage.supabase_session import SupabaseSession, SupabaseSessionStore


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
    def __init__(self, table: str, recorder: list):
        self.table = table
        self.recorder = recorder

    def upsert(self, payload):
        self.recorder.append(("upsert", self.table, payload))
        return self

    def update(self, payload):
        self.recorder.append(("update", self.table, payload))
        return self

    def eq(self, column, value):
        self.recorder.append(("eq", column, value))
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class FakeClient:
    def __init__(self, auth: FakeAuth):
        self.auth = auth
        self.calls: list = []

    def table(self, name: str) -> FakeTableQuery:
        return FakeTableQuery(name, self.calls)


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
