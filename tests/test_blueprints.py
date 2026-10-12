import pytest

from arc_companion.data.blueprints import (
    CATEGORIES,
    CATEGORY_ID_RANGES,
    load_blueprints,
)

_KNOWN_RARITIES = {"Common", "Uncommon", "Rare", "Epic", "Legendary"}


def test_loads_original_blueprints():
    # The count is not pinned: items are added over time. What must never
    # change is that the original 83 keep their ids (saved collections and
    # friends' cloud data are keyed on them).
    blueprints = {bp.id: bp for bp in load_blueprints()}
    assert set(range(1, 84)) <= set(blueprints)
    assert all(blueprints[i].category == "blueprint" for i in range(1, 84))


def test_spot_check_known_entries():
    blueprints = {bp.id: bp for bp in load_blueprints()}
    assert blueprints[1].name == "Extended Shotgun Mag III"
    assert blueprints[40].name == "Anvil"
    assert blueprints[83].name == "Snap Hook"


def test_ids_unique_and_inside_their_category_range():
    blueprints = load_blueprints()
    assert len({bp.id for bp in blueprints}) == len(blueprints)
    for bp in blueprints:
        assert bp.category in CATEGORIES
        low, high = CATEGORY_ID_RANGES[bp.category]
        assert low <= bp.id <= high


def test_rarity_is_none_or_known_value():
    for bp in load_blueprints():
        assert bp.rarity is None or bp.rarity in _KNOWN_RARITIES


def test_images_exist_or_item_is_a_placeholder():
    for bp in load_blueprints():
        if bp.image_path is None:
            continue  # placeholder: a known slot with no icon yet
        assert bp.image_path.parent.name == "images"
        assert bp.image_path.exists(), f"{bp.name}: missing {bp.image_path.name}"


def _write(tmp_path, body):
    path = tmp_path / "items.csv"
    path.write_text("id,name,image,rarity,category\n" + body, encoding="utf-8")
    return path


def test_old_file_without_category_column_loads_as_blueprints(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("id,name,image,rarity\n7,Thing,thing.png,Rare\n", encoding="utf-8")
    [item] = load_blueprints(path)
    assert (item.id, item.name, item.category, item.rarity) == (7, "Thing", "blueprint", "Rare")
    assert item.image_path.name == "thing.png"


def test_blank_image_is_a_placeholder(tmp_path):
    path = _write(tmp_path, "1001,Unknown Stencil #1,,,stencil\n")
    [item] = load_blueprints(path)
    assert item.image_path is None and item.category == "stencil" and item.rarity is None


@pytest.mark.parametrize(
    "body, message",
    [
        ("1,A,a.png,,widget\n", "unknown category"),
        ("1005,A,a.png,,blueprint\n", "outside the blueprint range"),
        ("5,A,a.png,,stencil\n", "outside the stencil range"),
        ("1,A,a.png,,blueprint\n1,B,b.png,,blueprint\n", "duplicate id"),
    ],
)
def test_malformed_item_files_fail_loudly(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        load_blueprints(_write(tmp_path, body))
