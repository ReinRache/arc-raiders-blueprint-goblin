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


# Real screenshots from a second player's account, submitted after their scan
# was misidentified as neither top- nor bottom-pinned. Root cause: a bright
# spot in the blurred game scene behind the panel (a light source) bled
# through at the same x-column as the scrollbar, at nearly the same y as in
# both screenshots -- _scrollbar_thumb_bounds's old global-min/max approach
# combined that stray bright run with the real thumb's run into one bogus,
# much-too-tall span. Fixed by taking the longest *contiguous* bright run
# instead (see screenshot_reader.py). Filenames here reflect each image's
# real (measured) scroll state, not the player's original filenames, which
# had the two swapped -- harmless for the app itself (scroll state is
# detected from pixels, never from a filename), but worth not perpetuating
# in the test suite. Ground truth is the in-panel "FOUND: 50/83" counter.
SECOND_PLAYER_FOUND_COUNT = 50


@pytest.fixture
def second_player_images():
    fixture_dir = FIXTURES / "scrollbar_background_bleed"
    top = sr.load_image(fixture_dir / "scrolled_top.png")
    bottom = sr.load_image(fixture_dir / "scrolled_bottom.png")
    return top, bottom


def test_scroll_position_survives_background_bleed_through(second_player_images):
    top_image, bottom_image = second_player_images
    assert sr.is_pinned_top(top_image)
    assert not sr.is_pinned_bottom(top_image)
    assert sr.is_pinned_bottom(bottom_image)
    assert not sr.is_pinned_top(bottom_image)


def test_pair_validates_despite_background_bleed_through(second_player_images):
    top_image, bottom_image = second_player_images
    top_grid = sr.read_grid(top_image, pinned_top=True)
    bottom_grid = sr.read_grid(bottom_image, pinned_top=False)
    result = validate_pair(top_grid, bottom_grid)
    assert result.ok, result.error


def test_merge_found_ids_matches_in_panel_counter_despite_background_bleed_through(second_player_images):
    top_image, bottom_image = second_player_images
    top_grid = sr.read_grid(top_image, pinned_top=True)
    bottom_grid = sr.read_grid(bottom_image, pinned_top=False)
    found = merge_found_ids(top_grid, bottom_grid)
    assert len(found) == SECOND_PLAYER_FOUND_COUNT


def test_pinned_top_detection_ignores_stray_bright_pixel_elsewhere_in_column():
    # Minimal synthetic reproduction of the background-bleed-through bug
    # above, isolated to just the scrollbar column logic rather than a full
    # real screenshot.
    import numpy as np

    from arc_companion.vision.grid_calibration import REFERENCE_HEIGHT, REFERENCE_WIDTH, SCROLLBAR_TRACK_TOP, SCROLLBAR_X

    image = np.zeros((REFERENCE_HEIGHT, REFERENCE_WIDTH, 3), dtype=np.uint8)
    # A real thumb pinned to the top: one solid bright run starting at the
    # track's top, covering a plausible fraction of the track.
    thumb_bottom = SCROLLBAR_TRACK_TOP + 300
    image[SCROLLBAR_TRACK_TOP:thumb_bottom, SCROLLBAR_X] = 255
    # A short, unrelated bright spot well below the thumb -- e.g. a light
    # source in the blurred game scene bleeding through the panel's
    # translucent background -- that a naive global min/max over the whole
    # column would incorrectly merge into the thumb's span.
    image[thumb_bottom + 200 : thumb_bottom + 210, SCROLLBAR_X] = 255

    assert sr.is_pinned_top(image)
    assert not sr.is_pinned_bottom(image)
