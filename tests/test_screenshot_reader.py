from pathlib import Path

import pytest

from arc_companion.vision import screenshot_reader as sr
from arc_companion.vision.import_merge import merge_found_ids, validate_pair

FIXTURES = Path(__file__).parent / "fixtures"

# Hand-verified by the designer against their actual account (not a guess or
# an inference from the "FOUND: 47/83" counter) — the complete found set for
# both reference screenshots, grouped by row for reference:
#   row1: 2,3,4,5,7,9            row6: 52,53,54,55,56,57,58
#   row2: 11,14,15,17,19         row7: 61,62,68,69
#   row3: 21,22,24,25,26,28,30   row8: 71,72,73,74,75,78,80
#   row4: 31,35,38,39,40         row9: 83
#   row5: 42,44,47,49,50 (shared by both screenshots)
GROUND_TRUTH_FOUND = {
    2, 3, 4, 5, 7, 9,
    11, 14, 15, 17, 19,
    21, 22, 24, 25, 26, 28, 30,
    31, 35, 38, 39, 40,
    42, 44, 47, 49, 50,
    52, 53, 54, 55, 56, 57, 58,
    61, 62, 68, 69,
    71, 72, 73, 74, 75, 78, 80,
    83,
}
assert len(GROUND_TRUTH_FOUND) == 47  # matches "FOUND: 47/83" shown in both screenshots


@pytest.fixture
def top_image():
    return sr.load_image(FIXTURES / "blueprints_panel_top.png")


@pytest.fixture
def bottom_image():
    return sr.load_image(FIXTURES / "blueprints_panel_bottom.png")


def test_find_panel_accepts_real_screenshots(top_image, bottom_image):
    assert sr.find_panel(top_image)
    assert sr.find_panel(bottom_image)


def test_find_panel_rejects_wrong_size():
    import numpy as np

    blank = np.zeros((100, 100, 3), dtype=np.uint8)
    assert not sr.find_panel(blank)


def test_scroll_position_matches_filenames(top_image, bottom_image):
    assert sr.is_pinned_top(top_image)
    assert not sr.is_pinned_bottom(top_image)
    assert sr.is_pinned_bottom(bottom_image)
    assert not sr.is_pinned_top(bottom_image)


def test_top_and_bottom_screenshots_validate_as_a_pair(top_image, bottom_image):
    top_grid = sr.read_grid(top_image, pinned_top=True)
    bottom_grid = sr.read_grid(bottom_image, pinned_top=False)
    result = validate_pair(top_grid, bottom_grid)
    assert result.ok, result.error


def test_merge_found_ids_matches_hand_verified_ground_truth_exactly(top_image, bottom_image):
    top_grid = sr.read_grid(top_image, pinned_top=True)
    bottom_grid = sr.read_grid(bottom_image, pinned_top=False)
    found = merge_found_ids(top_grid, bottom_grid)
    assert found == GROUND_TRUTH_FOUND, (
        f"false positives={sorted(found - GROUND_TRUTH_FOUND)} "
        f"false negatives={sorted(GROUND_TRUTH_FOUND - found)}"
    )


# Multi-resolution support: screenshots the designer captured at common
# gaming resolutions other than the original 2556x1439 reference, to prove
# grid_calibration.py's proportional scaling (see geometry_for()) actually
# works on real screenshots, not just in theory. There's no hand-verified
# per-item ground truth for these captures (unlike GROUND_TRUTH_FOUND above)
# -- the account had progressed to 50 found blueprints by the time these were
# taken, confirmed only via the in-panel "FOUND: 50/83" counter visible in
# both screenshots -- so these tests check the aggregate count and pairing
# validation rather than an itemized set.
MULTI_RESOLUTION_FOUND_COUNT = 50


@pytest.fixture(params=["1920x1080", "2560x1440"])
def multi_resolution_images(request):
    resolution_dir = FIXTURES / "multi_resolution" / request.param
    top = sr.load_image(resolution_dir / "top.png")
    bottom = sr.load_image(resolution_dir / "bottom.png")
    return top, bottom


def test_find_panel_accepts_other_resolutions(multi_resolution_images):
    top_image, bottom_image = multi_resolution_images
    assert sr.find_panel(top_image)
    assert sr.find_panel(bottom_image)


def test_scroll_position_matches_filenames_at_other_resolutions(multi_resolution_images):
    top_image, bottom_image = multi_resolution_images
    assert sr.is_pinned_top(top_image)
    assert not sr.is_pinned_bottom(top_image)
    assert sr.is_pinned_bottom(bottom_image)
    assert not sr.is_pinned_top(bottom_image)


def test_top_and_bottom_validate_as_a_pair_at_other_resolutions(multi_resolution_images):
    top_image, bottom_image = multi_resolution_images
    top_grid = sr.read_grid(top_image, pinned_top=True)
    bottom_grid = sr.read_grid(bottom_image, pinned_top=False)
    result = validate_pair(top_grid, bottom_grid)
    assert result.ok, result.error


def test_merge_found_ids_matches_in_panel_counter_at_other_resolutions(multi_resolution_images):
    top_image, bottom_image = multi_resolution_images
    top_grid = sr.read_grid(top_image, pinned_top=True)
    bottom_grid = sr.read_grid(bottom_image, pinned_top=False)
    found = merge_found_ids(top_grid, bottom_grid)
    assert len(found) == MULTI_RESOLUTION_FOUND_COUNT
