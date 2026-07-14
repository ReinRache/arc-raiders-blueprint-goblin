from arc_companion.storage.local_store import LocalJSONStore


def test_load_state_missing_file_returns_empty_state(tmp_path):
    store = LocalJSONStore(path=tmp_path / "config.json")
    state = store.load_state("local_user")
    assert state.steam_id == "local_user"
    assert state.blueprints_owned == []
    assert state.blueprints_wanted == []


def test_save_and_reload_round_trip(tmp_path):
    path = tmp_path / "config.json"
    store = LocalJSONStore(path=path)

    state = store.load_state("local_user")
    state.blueprints_owned = [3, 7, 12]
    store.save_state(state)

    reloaded = LocalJSONStore(path=path).load_state("local_user")
    assert reloaded.blueprints_owned == [3, 7, 12]
    assert reloaded.blueprints_wanted == []
    assert reloaded.updated_at > 0


def test_load_state_different_user_id_is_ignored(tmp_path):
    path = tmp_path / "config.json"
    store = LocalJSONStore(path=path)
    state = store.load_state("local_user")
    state.blueprints_owned = [1]
    store.save_state(state)

    other = store.load_state("someone_else")
    assert other.blueprints_owned == []
