from arc_companion.data.blueprints import load_blueprints

_KNOWN_RARITIES = {"Common", "Uncommon", "Rare", "Epic", "Legendary"}


def test_loads_all_blueprints():
    blueprints = load_blueprints()
    assert len(blueprints) == 83


def test_spot_check_known_entries():
    blueprints = {bp.id: bp for bp in load_blueprints()}
    assert blueprints[1].name == "Extended Shotgun Mag III"
    assert blueprints[40].name == "Anvil"
    assert blueprints[83].name == "Snap Hook"


def test_rarity_is_none_or_known_value():
    for bp in load_blueprints():
        assert bp.rarity is None or bp.rarity in _KNOWN_RARITIES


def test_image_paths_point_into_images_dir():
    for bp in load_blueprints():
        assert bp.image_path.parent.name == "images"
