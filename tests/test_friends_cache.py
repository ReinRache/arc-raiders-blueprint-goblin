from arc_companion.storage.friends_cache import FriendProfileSnapshot, FriendsCacheStore


def test_load_missing_file_returns_empty_dict(tmp_path):
    store = FriendsCacheStore(path=tmp_path / "friends_cache.json")
    assert store.load() == {}


def test_save_and_reload_round_trip(tmp_path):
    path = tmp_path / "friends_cache.json"
    store = FriendsCacheStore(path=path)
    snapshots = {
        "GBLN-AAAAA": FriendProfileSnapshot(
            arbg_user_id="GBLN-AAAAA",
            steam_id="76561198000000000",
            blueprints_owned=[1, 2],
            blueprints_wanted=[3],
            blueprints_spare=[2],
        ),
        "GBLN-BBBBB": FriendProfileSnapshot(arbg_user_id="GBLN-BBBBB"),
    }
    store.save(snapshots)

    reloaded = FriendsCacheStore(path=path).load()
    assert reloaded["GBLN-AAAAA"].steam_id == "76561198000000000"
    assert reloaded["GBLN-AAAAA"].blueprints_owned == [1, 2]
    assert reloaded["GBLN-AAAAA"].blueprints_wanted == [3]
    assert reloaded["GBLN-AAAAA"].blueprints_spare == [2]
    assert reloaded["GBLN-BBBBB"].steam_id is None
    assert reloaded["GBLN-BBBBB"].blueprints_owned == []


def test_save_overwrites_previous_contents(tmp_path):
    path = tmp_path / "friends_cache.json"
    store = FriendsCacheStore(path=path)
    store.save({"GBLN-AAAAA": FriendProfileSnapshot(arbg_user_id="GBLN-AAAAA")})
    store.save({"GBLN-BBBBB": FriendProfileSnapshot(arbg_user_id="GBLN-BBBBB")})

    reloaded = FriendsCacheStore(path=path).load()
    assert set(reloaded.keys()) == {"GBLN-BBBBB"}
