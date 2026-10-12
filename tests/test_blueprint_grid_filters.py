import time

import customtkinter as ctk
import pytest

from arc_companion.data.blueprints import Blueprint
from arc_companion.domain.friends import FriendStatusCounts
from arc_companion.domain.status import BlueprintStatus
from arc_companion.ui.blueprint_grid import BlueprintGrid

_ITEMS = [
    Blueprint(1, "Anvil", None, "Rare", "blueprint"),
    Blueprint(2, "Trigger Nade", None, "Rare", "blueprint"),
    Blueprint(1001, "Cerulean", None, "Rare", "stencil"),
    Blueprint(1002, "Unknown Stencil #2", None, None, "stencil"),
    Blueprint(2001, "Chandelier", None, None, "design"),
]


@pytest.fixture(scope="module")
def grid(tk_root):
    root = tk_root
    frame = ctk.CTkFrame(root)
    frame.pack(fill="both", expand=True)
    g = BlueprintGrid(
        frame,
        blueprints=_ITEMS,
        status_for_id=lambda _id: BlueprintStatus.UNOWNED,
        on_cycle=lambda _id: None,
        friend_counts_for_id=lambda _id: FriendStatusCounts(),
    )
    g.pack(fill="both", expand=True)
    # The grid's first render is debounced (_RESIZE_DEBOUNCE_MS) behind the
    # first <Configure>, so let that settle before testing anything.
    for _ in range(3):
        root.update()
        time.sleep(0.25)
    yield root, g
    frame.destroy()


def _shown_ids(root, g):
    root.update()
    return {i for i, c in g.cards.items() if c.winfo_ismapped()}


def test_all_view_shows_every_category(grid):
    root, g = grid
    g.set_search_query("")
    g.set_category(None)
    assert _shown_ids(root, g) == {1, 2, 1001, 1002, 2001}


@pytest.mark.parametrize(
    "category, expected",
    [("blueprint", {1, 2}), ("stencil", {1001, 1002}), ("design", {2001})],
)
def test_category_view_shows_only_that_category(grid, category, expected):
    root, g = grid
    g.set_search_query("")
    g.set_category(category)
    assert _shown_ids(root, g) == expected
    g.set_category(None)


def test_search_applies_within_the_selected_category(grid):
    root, g = grid
    g.set_category("stencil")
    g.set_search_query("unknown")
    assert _shown_ids(root, g) == {1002}
    g.set_search_query("anvil")  # exists, but in another category
    assert _shown_ids(root, g) == set()
    g.set_search_query("")
    g.set_category(None)
    assert _shown_ids(root, g) == {1, 2, 1001, 1002, 2001}
