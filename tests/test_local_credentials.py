from arc_companion.storage.local_credentials import LocalCredentials, LocalCredentialsStore


def test_load_missing_file_returns_empty_credentials(tmp_path):
    store = LocalCredentialsStore(path=tmp_path / "credentials.json")
    creds = store.load()
    assert creds.steam_web_api_key is None


def test_save_and_reload_round_trip(tmp_path):
    path = tmp_path / "credentials.json"
    store = LocalCredentialsStore(path=path)
    store.save(LocalCredentials(steam_web_api_key="ABCDEF1234567890"))

    reloaded = LocalCredentialsStore(path=path).load()
    assert reloaded.steam_web_api_key == "ABCDEF1234567890"
