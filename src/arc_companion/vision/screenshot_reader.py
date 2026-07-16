from pathlib import Path

import numpy as np
from PIL import Image

from arc_companion.vision.grid_calibration import (
    BOOK_ICON_REL_X,
    BOOK_ICON_REL_Y,
    CELL_PITCH,
    COLUMNS_PER_ROW,
    EXPECTED_HEIGHT,
    EXPECTED_WIDTH,
    GRID_ORIGIN_X,
    GRID_ORIGIN_Y_BOTTOM,
    GRID_ORIGIN_Y_TOP,
    OWNED_ICON_BRIGHTNESS_THRESHOLD,
    SCROLLBAR_PIN_TOLERANCE,
    SCROLLBAR_TRACK_BOTTOM,
    SCROLLBAR_TRACK_TOP,
    SCROLLBAR_X,
    WIDTH_TOLERANCE,
    blueprint_id_for_position,
    cell_origin,
    readable_rows_for_scroll,
    visible_rows_for_scroll,
)


def load_image(path: str | Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def _has_border_near(image: np.ndarray, origin_y: int) -> bool:
    """Checks a small window below-right of a cell's top-left corner for the
    border line, rather than a single exact pixel — robust to the couple of
    pixels of jitter observed between the two reference screenshots (the
    Bottom one is 3px wider than Top, and its grid sits ~2px further right)
    and to how far the rounded corner extends before the border goes straight."""
    height, width = image.shape[:2]
    x0, x1 = max(0, GRID_ORIGIN_X - 1), min(width, GRID_ORIGIN_X + 6)
    y0, y1 = origin_y + 10, min(height, origin_y + 30)
    if y0 >= height or x0 >= x1 or y0 >= y1:
        return False
    region = image[y0:y1, x0:x1]
    return bool((region.astype(float).sum(axis=2) > 150).any())


def find_panel(image: np.ndarray) -> bool:
    """Confirms this looks like a Blueprints-panel screenshot at the expected
    resolution. Returns False (not an exception) so callers can show a plain
    retry message rather than a stack trace."""
    height, width = image.shape[:2]
    if abs(width - EXPECTED_WIDTH) > WIDTH_TOLERANCE or abs(height - EXPECTED_HEIGHT) > WIDTH_TOLERANCE:
        return False
    # Cell (1, 1)'s left border is visible near the top when scrolled to the
    # top; GRID_ORIGIN_Y_BOTTOM's slot 0 is mostly clipped off-screen when
    # scrolled to the bottom, so check slot 1 (one cell down) there instead,
    # which is always fully visible. A screenshot of anything else won't have
    # this exact bright pixel pattern at either position, and we don't yet
    # know which scroll direction this screenshot is (checked separately).
    return _has_border_near(image, GRID_ORIGIN_Y_TOP) or _has_border_near(
        image, GRID_ORIGIN_Y_BOTTOM + CELL_PITCH
    )


def _scrollbar_thumb_bounds(image: np.ndarray) -> tuple[int, int] | None:
    height = image.shape[0]
    if SCROLLBAR_X >= image.shape[1]:
        return None
    brightness = image[:, SCROLLBAR_X].astype(float).sum(axis=1)
    bright_ys = np.where(brightness > 200)[0]
    if len(bright_ys) == 0:
        return None
    return int(bright_ys.min()), int(bright_ys.max())


def is_pinned_top(image: np.ndarray) -> bool:
    bounds = _scrollbar_thumb_bounds(image)
    if bounds is None:
        return False
    thumb_top, _ = bounds
    return abs(thumb_top - SCROLLBAR_TRACK_TOP) <= SCROLLBAR_PIN_TOLERANCE


def is_pinned_bottom(image: np.ndarray) -> bool:
    bounds = _scrollbar_thumb_bounds(image)
    if bounds is None:
        return False
    _, thumb_bottom = bounds
    return abs(thumb_bottom - SCROLLBAR_TRACK_BOTTOM) <= SCROLLBAR_PIN_TOLERANCE


def _is_owned_icon_present(image: np.ndarray, cell_x: int, cell_y: int) -> bool:
    x0, x1 = cell_x + BOOK_ICON_REL_X[0], cell_x + BOOK_ICON_REL_X[1]
    y0, y1 = cell_y + BOOK_ICON_REL_Y[0], cell_y + BOOK_ICON_REL_Y[1]
    if y1 > image.shape[0] or x1 > image.shape[1]:
        return False
    region = image[y0:y1, x0:x1]
    if region.size == 0:
        return False
    mean_brightness = region.astype(float).sum(axis=2).mean()
    return bool(mean_brightness > OWNED_ICON_BRIGHTNESS_THRESHOLD)


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
            x, y = cell_origin(visible_row_index, col, pinned_top)
            results[blueprint_id] = _is_owned_icon_present(image, x, y)
    return results
