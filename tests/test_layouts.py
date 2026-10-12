import pytest

from arc_companion.data.blueprints import CATEGORIES, load_blueprints
from arc_companion.data.layouts import layout_path, load_layout


def test_blueprint_layout_is_todays_positional_order():
    # Regression anchor: the data-driven layout must reproduce the old
    # (row-1)*10+col formula exactly, or existing scans would misread.
    assert load_layout("blueprint") == list(range(1, 84))


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
