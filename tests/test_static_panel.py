"""The Frozen Trail collection screens: one non-scrolling grid per tab.

Ground truth (tests/fixtures/frozen_trail/ground_truth.json) was listed by hand
from the in-game screens, tile by tile, and matches each tab's own FOUND
counter (47/91 blueprints, 5/14 stencils, 37/100 designs) -- 205 cells.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from arc_companion.vision import screenshot_reader as sr
from arc_companion.vision import static_panel
from arc_companion.vision.import_merge import validate_panel_screenshot

_FIXTURES = Path(__file__).parent / "fixtures" / "frozen_trail"
_TRUTH = json.loads((_FIXTURES / "ground_truth.json").read_text(encoding="utf-8"))
_SPECS = static_panel.load_static_specs()
_CATEGORIES = ["blueprint", "stencil", "design"]
# Native 2560x1440, plus downscales -- icon boxes shrink with resolution.
_SIZES = [(2560, 1440), (1920, 1080), (1600, 900), (1280, 720)]


def _image(category: str, size: tuple[int, int]) -> np.ndarray:
    img = Image.open(_FIXTURES / f"{category}.png").convert("RGB")
    if img.size != size:
        img = img.resize(size, Image.LANCZOS)
    return np.array(img)


def _layout(category: str) -> list[int]:
    return list(range(1, len(_TRUTH[category]["tiles"]) + 1))  # cell numbers stand in for item ids


def _expected(category: str) -> dict[int, bool]:
    return {t["n"]: t["found"] for t in _TRUTH[category]["tiles"]}


def test_ground_truth_matches_the_in_game_counters():
    for category, data in _TRUTH.items():
        assert len(data["tiles"]) == data["total_counter"]
        assert sum(t["found"] for t in data["tiles"]) == data["found_counter"]


@pytest.mark.parametrize("size", _SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("category", _CATEGORIES)
def test_every_cell_matches_hand_listed_ground_truth(category, size):
    result = static_panel.read_static_grid(_image(category, size), _SPECS[category], _layout(category))
    wrong = {n: result[n] for n in result if result[n] != _expected(category)[n]}
    assert not wrong, f"{category} @ {size}: misread cells {wrong}"


@pytest.mark.parametrize("size", _SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("category", _CATEGORIES)
def test_active_tab_is_identified(category, size):
    assert static_panel.active_tab(_image(category, size), _SPECS[category]) == category


@pytest.mark.parametrize("category", _CATEGORIES)
def test_validation_accepts_the_right_tab(category):
    outcome = validate_panel_screenshot(_image(category, (2560, 1440)), category, _SPECS[category], _layout(category))
    assert outcome.ok and outcome.grid_result == _expected(category)


@pytest.mark.parametrize("scanned_as, actual", [("blueprint", "design"), ("design", "blueprint"), ("stencil", "blueprint")])
def test_validation_rejects_a_screenshot_of_a_different_tab(scanned_as, actual):
    # Blueprints and Designs have IDENTICAL geometry -- the tab check is the
    # only thing standing between a Designs screenshot and silent misreading.
    outcome = validate_panel_screenshot(
        _image(actual, (2560, 1440)), scanned_as, _SPECS[scanned_as], _layout(scanned_as)
    )
    assert not outcome.ok
    assert "tab" in outcome.error and _SPECS[actual].label in outcome.error


def test_validation_rejects_a_screen_with_no_tab_bar():
    legacy = sr.load_image(Path(__file__).parent / "fixtures" / "blueprints_panel_top.png")
    blank = np.zeros((1440, 2560, 3), dtype=np.uint8)
    for image in (blank, np.array(Image.fromarray(legacy).resize((2560, 1440)))):
        outcome = validate_panel_screenshot(image, "blueprint", _SPECS["blueprint"], _layout("blueprint"))
        assert not outcome.ok and "tab bar" in outcome.error


def test_validation_rejects_a_wrong_shape_screenshot():
    squareish = np.zeros((1000, 1200, 3), dtype=np.uint8)
    outcome = validate_panel_screenshot(squareish, "stencil", _SPECS["stencil"], _layout("stencil"))
    assert not outcome.ok and "16:9" in outcome.error
