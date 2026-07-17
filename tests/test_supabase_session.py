from arc_companion.storage.supabase_session import SupabaseSession, SupabaseSessionStore


def test_load_missing_file_returns_empty_session(tmp_path):
    store = SupabaseSessionStore(path=tmp_path / "supabase_session.json")
    session = store.load()
    assert session.access_token is None
    assert session.refresh_token is None


def test_save_and_reload_round_trip(tmp_path):
    path = tmp_path / "supabase_session.json"
    store = SupabaseSessionStore(path=path)
    store.save(SupabaseSession(access_token="access-abc", refresh_token="refresh-xyz"))

    reloaded = SupabaseSessionStore(path=path).load()
    assert reloaded.access_token == "access-abc"
    assert reloaded.refresh_token == "refresh-xyz"
