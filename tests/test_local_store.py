import json

from arc_companion.identity import is_valid_arbg_id
from arc_companion.storage.local_store import LocalJSONStore


def test_load_state_missing_file_generates_fresh_identity(tmp_path):
    store = LocalJSONStore(path=tmp_path / "config.json")
    state = store.load_state()
    assert is_valid_arbg_id(state.arbg_user_id)
    assert state.steam_id is None
    assert state.arbg_friend_user_ids == []
    assert state.blueprints_owned == []
    assert state.blueprints_wanted == []
    assert state.blueprints_spare == []
    assert state.recovery_secret  # non-empty -- generated fresh alongside arbg_user_id


def test_save_and_reload_round_trip(tmp_path):
    path = tmp_path / "config.json"
    store = LocalJSONStore(path=path)

    state = store.load_state()
    state.blueprints_owned = [3, 7, 12]
    state.blueprints_wanted = [9]
    state.blueprints_spare = [12]
    state.arbg_friend_user_ids = ["GBLN-ABCDE"]
    state.steam_id = "76561198000000000"
    store.save_state(state)

    reloaded = LocalJSONStore(path=path).load_state()
    assert reloaded.arbg_user_id == state.arbg_user_id
    assert reloaded.steam_id == "76561198000000000"
    assert reloaded.arbg_friend_user_ids == ["GBLN-ABCDE"]
    assert reloaded.blueprints_owned == [3, 7, 12]
    assert reloaded.blueprints_wanted == [9]
    assert reloaded.blueprints_spare == [12]
    assert reloaded.updated_at > 0
    assert reloaded.recovery_secret == state.recovery_secret


def test_identity_is_stable_across_reloads(tmp_path):
    path = tmp_path / "config.json"
    first = LocalJSONStore(path=path).load_state()
    LocalJSONStore(path=path).save_state(first)

    second = LocalJSONStore(path=path).load_state()
    assert second.arbg_user_id == first.arbg_user_id
    assert second.recovery_secret == first.recovery_secret


def test_migrates_legacy_local_user_placeholder_without_losing_progress(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "steam_id": "local_user",
                "blueprints_owned": [1, 2, 3],
                "blueprints_wanted": [4],
                "blueprints_spare": [3],
                "updated_at": 123,
            }
        ),
        encoding="utf-8",
    )

    state = LocalJSONStore(path=path).load_state()
    assert is_valid_arbg_id(state.arbg_user_id)
    assert state.steam_id is None  # the old placeholder was never a real SteamID
    assert state.blueprints_owned == [1, 2, 3]
    assert state.blueprints_wanted == [4]
    assert state.blueprints_spare == [3]


def test_migrates_legacy_file_missing_arbg_id_field_entirely(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"steam_id": "76561198000000000", "blueprints_owned": [5]}),
        encoding="utf-8",
    )

    state = LocalJSONStore(path=path).load_state()
    assert is_valid_arbg_id(state.arbg_user_id)
    assert state.steam_id == "76561198000000000"  # a real steam_id is preserved, not just the placeholder
    assert state.blueprints_owned == [5]


def test_backfills_recovery_secret_for_file_predating_the_field(tmp_path):
    # An install that existed before push_profile_with_recovery shipped --
    # has a real arbg_user_id already, just no recovery_secret key at all.
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"arbg_user_id": "GBLN-ABCDE", "blueprints_owned": [1]}),
        encoding="utf-8",
    )

    state = LocalJSONStore(path=path).load_state()
    assert state.arbg_user_id == "GBLN-ABCDE"  # untouched -- only recovery_secret is backfilled
    assert state.recovery_secret  # non-empty -- generated fresh
    assert state.blueprints_owned == [1]
