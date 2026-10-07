"""Regression: filtering while scrolled down used to strand the canvas view
past the end of the (much shorter) filtered list -- an empty grid until
something nudged the canvas. See BlueprintGrid._sync_scroll."""

import time
import tkinter

import customtkinter as ctk
import pytest

from arc_companion.data.blueprints import load_blueprints
from arc_companion.domain.friends import FriendStatusCounts, Highlight
from arc_companion.domain.status import BlueprintStatus
from arc_companion.ui.blueprint_grid import BlueprintGrid


# One Tk root for the whole file: repeatedly creating/destroying roots in a
# single process is flaky, and each test resets the state it touches.
@pytest.fixture(scope="module")
def grid():
    try:
        root = ctk.CTk()
    except tkinter.TclError:
        pytest.skip("no display available for Tk")
    root.geometry("1500x700")
    blueprints = load_blueprints()
    g = BlueprintGrid(
        root,
        blueprints=blueprints,
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
    root.destroy()


def _cards_in_view(root, g):
    root.update()
    canvas = g._parent_canvas
    top = canvas.canvasy(0)
    bottom = top + canvas.winfo_height()
    return [
        c for c in g.cards.values()
        if c.winfo_ismapped() and c.winfo_y() + c.winfo_height() > top and c.winfo_y() < bottom
    ]


def test_filtering_after_scrolling_down_still_shows_results(grid):
    root, g = grid
    g.set_search_query("")
    g._parent_canvas.yview_moveto(0.8)
    root.update()
    assert _cards_in_view(root, g)  # sanity: scrolled, but content is visible

    g.set_search_query("tr")

    expected = [bp for bp in g.blueprints if "tr" in bp.name.lower()]
    assert expected, "test data should have at least one 'tr' blueprint"
    assert len(_cards_in_view(root, g)) == len(expected)
    assert g._parent_canvas.yview()[0] == 0.0


def test_clearing_the_filter_restores_the_full_list(grid):
    root, g = grid
    g.set_search_query("tr")
    g.set_search_query("")
    assert len(_cards_in_view(root, g)) > len([bp for bp in g.blueprints if "tr" in bp.name.lower()])
    assert g._parent_canvas.bbox("all")[3] > g._parent_canvas.winfo_height()
