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


# ---- "Show:" status / trade filters ------------------------------------------


@pytest.fixture
def status_grid(tk_root):
    """A grid whose statuses and friend counts the test controls."""
    state = {
        "status": {
            1: BlueprintStatus.UNOWNED,
            2: BlueprintStatus.WANT,
            1001: BlueprintStatus.OWNED,
            1002: BlueprintStatus.HAVE,
            2001: BlueprintStatus.UNOWNED,
        },
        # a friend has a spare of 1 (I am UNOWNED -> thin green) and of 2 (I WANT it -> thick green);
        # a friend wants my spare 1002 (-> thick cyan)
        "counts": {
            1: FriendStatusCounts(have=["Ann"]),
            2: FriendStatusCounts(have=["Ann"]),
            1002: FriendStatusCounts(want=["Bo"]),
        },
    }
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    g = BlueprintGrid(
        frame,
        blueprints=_ITEMS,
        status_for_id=lambda i: state["status"][i],
        on_cycle=lambda _id: None,
        friend_counts_for_id=lambda i: state["counts"].get(i, FriendStatusCounts()),
    )
    g.pack(fill="both", expand=True)
    for _ in range(3):
        tk_root.update()
        time.sleep(0.25)
    yield tk_root, g, state
    frame.destroy()


@pytest.mark.parametrize(
    "key, expected",
    [
        ("all", {1, 2, 1001, 1002, 2001}),
        ("trades", {1, 2, 1002}),
        ("want", {2}),
        ("have", {1002}),
        ("owned", {1001, 1002}),  # a spare is a copy you own
        ("missing", {1, 2, 2001}),
    ],
)
def test_status_filters(status_grid, key, expected):
    root, g, _ = status_grid
    g.set_status_filter(key)
    assert _shown_ids(root, g) == expected


def test_filters_combine_with_category_and_search(status_grid):
    root, g, _ = status_grid
    g.set_status_filter("missing")
    g.set_category("blueprint")
    assert _shown_ids(root, g) == {1, 2}
    g.set_search_query("anvil")
    assert _shown_ids(root, g) == {1}


def test_a_status_change_under_a_filter_updates_the_view(status_grid):
    root, g, state = status_grid
    g.set_status_filter("want")
    assert _shown_ids(root, g) == {2}
    state["status"][2] = BlueprintStatus.OWNED  # I just got it
    g.refresh_status(2)
    root.update()
    time.sleep(0.05)
    assert _shown_ids(root, g) == set()


def test_unknown_filter_is_rejected(status_grid):
    _, g, _ = status_grid
    with pytest.raises(ValueError):
        g.set_status_filter("bogus")
