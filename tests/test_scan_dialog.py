"""Drives the real ScanDialog with the hand-verified Frozen Trail screenshots."""

import json
from pathlib import Path

import pytest

from arc_companion.data.blueprints import load_blueprints
from arc_companion.data.layouts import load_layout
from arc_companion.ui.scan_dialog import ScanDialog

_FIX = Path(__file__).parent / "fixtures" / "frozen_trail"
_TRUTH = json.loads((_FIX / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture
def dialog(tk_root):
    applied = []
    items = load_blueprints()
    dlg = ScanDialog(
        tk_root,
        blueprints=items,
        owned_ids={1, 2, 3},
        wanted_ids=set(),
        spare_ids=set(),
        on_apply=lambda o, w, s: applied.append((o, w, s)),
    )
    dlg.applied = applied
    tk_root.update()
    yield dlg
    if dlg.winfo_exists():
        dlg.destroy()


def _found_ids(category):
    layout = load_layout(category)
    return {layout[t["n"] - 1] for t in _TRUTH[category]["tiles"] if t["found"]}


def test_one_screenshot_per_tab_and_apply(dialog, tk_root):
    assert str(dialog.review_btn.cget("state")) == "disabled"  # nothing chosen yet

    dialog._validate_and_report(str(_FIX / "stencil.png"), "stencil")
    tk_root.update()
    assert "5 of 14" in dialog._status_labels["stencil"].cget("text")
    assert str(dialog.review_btn.cget("state")) == "normal"

    dialog._show_review()
    tk_root.update()
    # only the Stencils tab was scanned: the 3 owned blueprints are out of scope,
    # so they're neither "missing" nor in need of confirmation
    assert dialog.merge_outcome.regression_ids == set()
    assert dialog.merge_outcome.newly_found_ids == _found_ids("stencil")

    dialog._apply_upgrade_only()
    [(owned, _, _)] = dialog.applied
    assert owned == {1, 2, 3} | _found_ids("stencil")


def test_all_three_tabs(dialog, tk_root):
    for category in ("blueprint", "stencil", "design"):
        dialog._validate_and_report(str(_FIX / f"{category}.png"), category)
    tk_root.update()
    dialog._show_review()
    expected = _found_ids("blueprint") | _found_ids("stencil") | _found_ids("design")
    assert dialog.scan_found_ids == expected
    assert len(expected) == 47 + 5 + 37  # the three in-game FOUND counters


def test_wrong_tab_is_rejected_with_a_clear_message(dialog, tk_root):
    # a Designs screenshot offered for the Blueprints tab (identical geometry!)
    dialog._validate_and_report(str(_FIX / "design.png"), "blueprint")
    tk_root.update()
    text = dialog._status_labels["blueprint"].cget("text")
    assert "Designs tab" in text and "Blueprints tab was expected" in text
    assert "blueprint" not in dialog.grids
    assert str(dialog.review_btn.cget("state")) == "disabled"


def test_back_keeps_chosen_screenshots(dialog, tk_root):
    dialog._validate_and_report(str(_FIX / "stencil.png"), "stencil")
    dialog._show_review()
    dialog._back_to_pick()
    tk_root.update()
    assert "5 of 14" in dialog._status_labels["stencil"].cget("text")
    assert str(dialog.review_btn.cget("state")) == "normal"
