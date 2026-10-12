import pytest

from arc_companion.data.blueprints import CATEGORIES, load_blueprints
from arc_companion.data.layouts import layout_path, load_layout


def test_legacy_layout_still_reproduces_the_old_positional_order():
    # Regression anchor for the pre-Frozen-Trail scanner fixtures: the legacy
    # layout is a fixed constant, independent of the (now reordered) shipped
    # blueprint layout.
    from arc_companion.vision.grid_calibration import LEGACY_LAYOUT

    assert list(LEGACY_LAYOUT) == list(range(1, 84))


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_shipped_layout_is_valid(category):
    if not layout_path(category).exists():
        pytest.skip(f"no {category} layout yet")
    items = {bp.id: bp for bp in load_blueprints()}
    layout = load_layout(category, known_ids=set(items))
    assert all(items[i].category == category for i in layout), "layout mixes categories"


def test_layout_rejects_unknown_and_duplicate_ids(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("item_id\n1\n2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not in blueprints.csv"):
        load_layout("blueprint", known_ids={1}, path=path)
    path.write_text("item_id\n1\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="more than once"):
        load_layout("blueprint", known_ids={1}, path=path)


def test_inserting_an_item_mid_grid_is_just_a_line(tmp_path):
    # The point of the file: the game adds an item in the middle -> new id,
    # one new line; existing ids are untouched and just shift position.
    path = tmp_path / "x.csv"
    path.write_text("item_id\n1\n2\n84\n3\n", encoding="utf-8")
    assert load_layout("blueprint", known_ids={1, 2, 3, 84}, path=path) == [1, 2, 84, 3]


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_item_is_placed_on_its_screen(category):
    # An item missing from its layout could never be credited by a scan, and
    # would silently stay "not found" forever -- so adding an item means BOTH
    # a row in blueprints.csv and a line in its layout file.
    items = load_blueprints()
    layout = set(load_layout(category))
    missing = [bp.name for bp in items if bp.category == category and bp.id not in layout]
    assert not missing, f"in blueprints.csv but not in data/layouts/{category}.csv: {missing}"


def test_ordered_items_follows_layouts_and_keeps_unplaced_items():
    from arc_companion.data.blueprints import Blueprint
    from arc_companion.data.layouts import ordered_items

    items = [
        Blueprint(1, "A", None, None, "blueprint"),
        Blueprint(2, "B", None, None, "blueprint"),
        Blueprint(1001, "S", None, None, "stencil"),
    ]
    ordered = ordered_items(items)
    # real shipped layouts reference ids not in this tiny list: those are skipped,
    # and items the layouts don't mention are kept (appended per category)
    assert {bp.id for bp in ordered} == {1, 2, 1001}
    assert [bp.category for bp in ordered] == ["blueprint", "blueprint", "stencil"]


def test_shipped_order_mirrors_the_in_game_screen():
    from arc_companion.data.layouts import ordered_items

    ordered = ordered_items(load_blueprints())
    by_category = {c: [bp.id for bp in ordered if bp.category == c] for c in CATEGORIES}
    for category in CATEGORIES:
        assert by_category[category] == load_layout(category)


def test_report_a_missing_item_link_points_at_the_issue_form():
    from arc_companion.ui.options_dialog import report_missing_item_url

    assert report_missing_item_url("o/r") == "https://github.com/o/r/issues/new?template=missing_item.yml"
    assert report_missing_item_url(None) == ""
