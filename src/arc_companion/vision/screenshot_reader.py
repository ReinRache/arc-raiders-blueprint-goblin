import dataclasses
from pathlib import Path

import numpy as np
from PIL import Image

from arc_companion.vision.grid_calibration import (
    COLUMNS_PER_ROW,
    OWNED_ICON_BRIGHTNESS_THRESHOLD,
    GridGeometry,
    blueprint_id_for_position,
    cell_origin,
    geometry_for,
    is_plausible_aspect_ratio,
    readable_rows_for_scroll,
    visible_rows_for_scroll,
)

# Row index (0-based, within the viewport) used to empirically refine the Y
# origin per screenshot -- see refine_geometry(). Deliberately not the first
# readable row: for a bottom-pinned scroll, the first readable row sits right
# next to the clipped slot-0/header-text boundary, where a probe can latch
# onto the wrong bright feature (confirmed directly -- an early attempt using
# that row produced a noisy, wrong-signed correction; a safely-interior row
# didn't).
_TOP_REFINEMENT_ROW_INDEX = 2
_BOTTOM_REFINEMENT_ROW_INDEX = 3
_REFINEMENT_SEARCH_RADIUS = 15  # px, at the screenshot's own actual resolution
_REFINEMENT_PROBE_X_OFFSET = 10  # px past the rounded corner, before the border goes straight


def load_image(path: str | Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def _has_border_near(image: np.ndarray, geometry: GridGeometry, origin_y: float) -> bool:
    """Checks a small window below-right of a cell's top-left corner for the
    border line, rather than a single exact pixel — robust to a few pixels
    of jitter (already observed between the reference screenshots
    themselves, and confirmed to be a similar order of magnitude across
    different resolutions) and to how far the rounded corner extends before
    the border goes straight."""
    height, width = image.shape[:2]
    x_lo, x_hi = geometry.border_check_window_x
    y_lo, y_hi = geometry.border_check_window_y
    x0, x1 = max(0, round(geometry.origin_x + x_lo)), min(width, round(geometry.origin_x + x_hi))
    y0, y1 = round(origin_y + y_lo), min(height, round(origin_y + y_hi))
    if y0 >= height or x0 >= x1 or y0 >= y1:
        return False
    region = image[y0:y1, x0:x1]
    return bool((region.astype(float).sum(axis=2) > 150).any())


def find_panel(image: np.ndarray) -> bool:
    """Confirms this looks like a Blueprints-panel screenshot. Returns False
    (not an exception) so callers can show a plain retry message rather than
    a stack trace. Not tied to one fixed resolution — scales the calibrated
    geometry to the screenshot's actual size (see grid_calibration.py) and
    checks for the panel's real border pattern at the scaled position, after
    a cheap aspect-ratio sanity check to reject anything wildly different
    before doing that work."""
    height, width = image.shape[:2]
    if not is_plausible_aspect_ratio(width, height):
        return False
    geometry = geometry_for(width, height)
    # Cell (1, 1)'s left border is visible near the top when scrolled to the
    # top; the bottom-scroll origin's slot 0 is mostly clipped off-screen, so
    # check slot 1 (one cell down) there instead, which is always fully
    # visible. A screenshot of anything else won't have this exact bright
    # pixel pattern at either position, and we don't yet know which scroll
    # direction this screenshot is (checked separately).
    return _has_border_near(image, geometry, geometry.origin_y_top) or _has_border_near(
        image, geometry, geometry.origin_y_bottom + geometry.cell_pitch_y
    )


def _scrollbar_thumb_bounds(image: np.ndarray, geometry: GridGeometry) -> tuple[int, int] | None:
    scrollbar_x = round(geometry.scrollbar_x)
    if scrollbar_x >= image.shape[1]:
        return None
    brightness = image[:, scrollbar_x].astype(float).sum(axis=1)
    bright_ys = np.where(brightness > 200)[0]
    if len(bright_ys) == 0:
        return None
    # The real thumb is one contiguous bright run, but a bright spot in the
    # blurred game scene behind the panel (e.g. a light source) can bleed
    # through the panel's translucent background at this same x-coordinate
    # and show up as its own short, separate run elsewhere in the column --
    # confirmed against real screenshots where this produced a bogus,
    # much-too-tall combined span from a naive global min/max. Taking the
    # longest contiguous run instead is immune to that: the thumb always
    # spans a large, fixed fraction of the track (ROWS_PER_VIEWPORT of
    # TOTAL_ROWS), far longer than a stray few-pixel bright spot.
    runs: list[tuple[int, int]] = []
    run_start = bright_ys[0]
    prev = bright_ys[0]
    for y in bright_ys[1:]:
        if y != prev + 1:
            runs.append((run_start, prev))
            run_start = y
        prev = y
    runs.append((run_start, prev))
    thumb_top, thumb_bottom = max(runs, key=lambda run: run[1] - run[0])
    return int(thumb_top), int(thumb_bottom)


def is_pinned_top(image: np.ndarray) -> bool:
    height, width = image.shape[:2]
    geometry = geometry_for(width, height)
    bounds = _scrollbar_thumb_bounds(image, geometry)
    if bounds is None:
        return False
    thumb_top, _ = bounds
    return abs(thumb_top - geometry.scrollbar_track_top) <= geometry.scrollbar_pin_tolerance


def is_pinned_bottom(image: np.ndarray) -> bool:
    height, width = image.shape[:2]
    geometry = geometry_for(width, height)
    bounds = _scrollbar_thumb_bounds(image, geometry)
    if bounds is None:
        return False
    _, thumb_bottom = bounds
    return abs(thumb_bottom - geometry.scrollbar_track_bottom) <= geometry.scrollbar_pin_tolerance


def _is_owned_icon_present(
    image: np.ndarray, geometry: GridGeometry, cell_x: float, cell_y: float
) -> bool:
    x0, x1 = round(cell_x + geometry.book_icon_rel_x[0]), round(cell_x + geometry.book_icon_rel_x[1])
    y0, y1 = round(cell_y + geometry.book_icon_rel_y[0]), round(cell_y + geometry.book_icon_rel_y[1])
    if y1 > image.shape[0] or x1 > image.shape[1]:
        return False
    region = image[y0:y1, x0:x1]
    if region.size == 0:
        return False
    mean_brightness = region.astype(float).sum(axis=2).mean()
    # A color value, not a spatial measurement -- does not scale with resolution.
    return bool(mean_brightness > OWNED_ICON_BRIGHTNESS_THRESHOLD)


def _find_nearby_border_y(image: np.ndarray, x: int, y_guess: int, search_radius: int) -> int | None:
    """Scans vertically for a thin horizontal border line near y_guess.
    Distinguished from broad bright UI elements like text by requiring the
    brightness to be a narrow peak -- bright at y, notably dimmer 3px above
    and 3px below, not a broad plateau -- since a plain brightest-pixel
    search was confirmed to lock onto in-panel text instead of real cell
    borders."""
    height = image.shape[0]
    candidates = []
    for y in range(max(3, y_guess - search_radius), min(height - 3, y_guess + search_radius)):
        center = image[y, x].astype(float).sum()
        above = image[y - 3, x].astype(float).sum()
        below = image[y + 3, x].astype(float).sum()
        if center > 150 and center - above > 40 and center - below > 40:
            candidates.append((y, center))
    if not candidates:
        return None
    candidates.sort(key=lambda c: abs(c[0] - y_guess))
    return candidates[0][0]


def refine_geometry(image: np.ndarray, geometry: GridGeometry, pinned_top: bool) -> GridGeometry:
    """Corrects the formula-scaled Y origin using one real border measurement
    from THIS screenshot. Confirmed empirically necessary: real screenshots
    at 1920x1080 showed a small but consistent few-pixel offset from the pure
    formula prediction, enough to misread cells near the bottom of a
    viewport. That offset is a CONSTANT shift, not a compounding pitch error
    (confirmed by checking deltas across multiple rows), so one anchor
    measurement suffices -- no need to re-derive cell pitch from scratch.
    Falls back to the unrefined geometry if no border is found near the
    predicted position (e.g. an unexpected screenshot crop)."""
    height, width = image.shape[:2]
    x_probe = round(geometry.origin_x + _REFINEMENT_PROBE_X_OFFSET)
    if x_probe >= width:
        return geometry
    row_index = _TOP_REFINEMENT_ROW_INDEX if pinned_top else _BOTTOM_REFINEMENT_ROW_INDEX
    base = geometry.origin_y_top if pinned_top else geometry.origin_y_bottom
    predicted = round(base + row_index * geometry.cell_pitch_y)
    found = _find_nearby_border_y(image, x_probe, predicted, _REFINEMENT_SEARCH_RADIUS)
    if found is None:
        return geometry
    shift = found - predicted
    if pinned_top:
        return dataclasses.replace(geometry, origin_y_top=geometry.origin_y_top + shift)
    return dataclasses.replace(geometry, origin_y_bottom=geometry.origin_y_bottom + shift)


def read_grid(image: np.ndarray, pinned_top: bool) -> dict[int, bool]:
    """Reads every blueprint id in this screenshot's *reliably readable* rows
    (see readable_rows_for_scroll — the one row-slot at the viewport's outer
    edge is skipped, since it's clipped by the panel's own chrome and is
    always covered by the other screenshot in a top+bottom pair anyway) to
    whether it's owned (its book-category icon is rendered — see
    grid_calibration.py for why that's used instead of the checkmark badge).
    Includes not-found ids too — callers that only want the found set should
    filter for True values; the full dict is what lets validate_pair()
    cross-check the one row genuinely shared between a top and bottom
    submission."""
    height, width = image.shape[:2]
    geometry = refine_geometry(image, geometry_for(width, height), pinned_top)
    results: dict[int, bool] = {}
    all_rows = visible_rows_for_scroll(pinned_top)
    readable = set(readable_rows_for_scroll(pinned_top))
    for visible_row_index, logical_row in enumerate(all_rows):
        if logical_row not in readable:
            continue
        for col in range(1, COLUMNS_PER_ROW + 1):
            blueprint_id = blueprint_id_for_position(logical_row, col)
            if blueprint_id is None:
                continue
            x, y = cell_origin(visible_row_index, col, pinned_top, geometry)
            results[blueprint_id] = _is_owned_icon_present(image, geometry, x, y)
    return results
