"""On-screen order of each category's collection grid, as editable data.

Item ids (data/blueprints.csv) are stable forever; *where an item sits on the
in-game screen* is not -- the game inserts new items mid-grid. Keeping the
screen order in its own file means a game update is "add one item row, insert
one line here": no id renumbering, no code change, no cloud/data migration.

data/layouts/<category>.csv has one column, `item_id`, listing items in
reading order (left-to-right, top-to-bottom). Row/column are derived from an
item's index and the grid's column count (see vision/grid_calibration.py), and
the number of cells is simply the list's length.
"""

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from arc_companion.paths import resource_root

if TYPE_CHECKING:
    from arc_companion.data.blueprints import Blueprint

LAYOUTS_DIR = resource_root() / "data" / "layouts"


def layout_path(category: str) -> Path:
    return LAYOUTS_DIR / f"{category}.csv"


def load_layout(category: str, known_ids: set[int] | None = None, path: Path | None = None) -> list[int]:
    """Item ids in on-screen order. With `known_ids`, also validates the file
    (every id exists in the item list, none repeated) -- raising ValueError,
    since a wrong hand edit here would make the scanner credit the wrong items."""
    path = path or layout_path(category)
    ids: list[int] = []
    with open(path, newline="", encoding="utf-8") as f:
        for line_number, row in enumerate(csv.DictReader(f), start=2):
            ids.append(int(row["item_id"]))
    if known_ids is not None:
        seen: set[int] = set()
        for item_id in ids:
            if item_id not in known_ids:
                raise ValueError(f"{path.name}: id {item_id} is not in blueprints.csv")
            if item_id in seen:
                raise ValueError(f"{path.name}: id {item_id} appears more than once")
            seen.add(item_id)
    return ids


def ordered_items(items: list[Blueprint]) -> list[Blueprint]:
    """Items in the order the game shows them: category by category (Blueprints,
    Stencils, Designs), each in its layout file's order, so the app's grid
    mirrors the in-game screen. Anything missing from its layout (an item
    added to blueprints.csv but not yet placed) goes at the end of its
    category rather than disappearing."""
    from arc_companion.data.blueprints import CATEGORIES

    ordered: list = []
    for category in CATEGORIES:
        in_category = {bp.id: bp for bp in items if bp.category == category}
        placed = [i for i in load_layout(category) if i in in_category]
        ordered += [in_category[i] for i in placed]
        ordered += [bp for bp in items if bp.category == category and bp.id not in set(placed)]
    return ordered
