from arc_companion.paths import migrate_legacy_user_data


def test_copies_legacy_files_that_exist(tmp_path):
    legacy, new = tmp_path / "exe_dir", tmp_path / "appdata" / "App"
    legacy.mkdir()
    (legacy / "config.json").write_text("cfg")
    (legacy / "supabase_session.json").write_text("sess")
    (legacy / "unrelated.txt").write_text("x")

    migrate_legacy_user_data(legacy, new)

    assert (new / "config.json").read_text() == "cfg"
    assert (new / "supabase_session.json").read_text() == "sess"
    assert not (new / "friends_cache.json").exists()  # absent in legacy -> not invented
    assert not (new / "unrelated.txt").exists()  # only known files
    assert (legacy / "config.json").exists()  # copied, never moved


def test_never_overwrites_existing_data(tmp_path):
    legacy, new = tmp_path / "old", tmp_path / "new"
    legacy.mkdir()
    new.mkdir()
    (legacy / "config.json").write_text("OLD BUILD")
    (new / "config.json").write_text("CURRENT")

    migrate_legacy_user_data(legacy, new)

    assert (new / "config.json").read_text() == "CURRENT"


def test_fresh_install_just_creates_the_folder(tmp_path):
    legacy, new = tmp_path / "old", tmp_path / "new"
    legacy.mkdir()
    migrate_legacy_user_data(legacy, new)
    assert new.is_dir() and list(new.iterdir()) == []


def test_same_directory_is_a_noop(tmp_path):
    (tmp_path / "config.json").write_text("cfg")
    migrate_legacy_user_data(tmp_path, tmp_path)
    assert (tmp_path / "config.json").read_text() == "cfg"
