"""Pixel geometry for the in-game Blueprints panel, calibrated at a
REFERENCE_WIDTH x REFERENCE_HEIGHT resolution and scaled proportionally to
whatever resolution an actual screenshot turns out to be (see geometry_for()).

Confirmed empirically, not assumed, that the panel scales this way: real
screenshots captured at 1920x1080 and 2560x1440 both had every measured
corner land within a few pixels of what proportional scaling predicts --
well inside the tolerance this module's own border-detection already
absorbs (jitter of a similar size was already documented between the two
original 2556x1439-class reference screenshots themselves). See the "Vision"
section of CLAUDE.md for the full writeup, including a real mistake caught
along the way: an early manual pixel-measurement attempt misread which row
it was looking at and wrongly concluded the bottom-scroll origin didn't
scale -- precise designer-provided pixel coordinates (not eyeballed crops)
resolved it.

If the game patches in more blueprints later, TOTAL_BLUEPRINTS (and
data/blueprints.csv) are the values that need updating — the grid geometry
itself shouldn't need to change unless the panel layout changes too.
"""

from dataclasses import dataclass

REFERENCE_WIDTH = 2556
REFERENCE_HEIGHT = 1439
# How far an actual screenshot's aspect ratio may drift from the reference's
# before we don't trust proportional scaling to apply -- comfortably covers
# the ~0.1% jitter measured between 1920x1080, the 2556x1439-class
# reference, and 2560x1440, but won't accept a very different aspect ratio
# (e.g. ultrawide) that hasn't been verified against real data.
ASPECT_RATIO_TOLERANCE = 0.03

GRID_ORIGIN_X = 574
CELL_PITCH = 139

# The scrolled-to-top and scrolled-to-bottom views do NOT share one origin —
# bottom-anchored scrolling doesn't land on a clean multiple of CELL_PITCH
# from the top, confirmed empirically against the reference screenshots (a
# naive shared-origin assumption was off by ~130px and silently misread most
# of the bottom screenshot's grid). Each is measured and calibrated
# independently, both scale proportionally like everything else here:
GRID_ORIGIN_Y_TOP = 421  # row 1's top border, screenshot scrolled fully up
GRID_ORIGIN_Y_BOTTOM = 291  # row (TOTAL_ROWS - ROWS_PER_VIEWPORT + 1)'s top border,
# screenshot scrolled fully down — this is the *slot 0* origin, not row 1's;
# that row is mostly clipped off-screen, which is expected.

COLUMNS_PER_ROW = 10
TOTAL_BLUEPRINTS = 83
TOTAL_ROWS = -(-TOTAL_BLUEPRINTS // COLUMNS_PER_ROW)  # ceil division = 9
ROWS_PER_VIEWPORT = 6  # visible row-slots per screenshot; the last is often clipped

# A found blueprint's cell shows a small category "book" icon in the
# bottom-left corner, sitting on the cell's solid (opaque) name-label strip.
# An unowned slot is completely empty — no rendered icon anywhere in the
# cell, book icon included. This turned out to be a far more reliable
# ownership signal than the checkmark badge near the top-right corner (see
# git history / the OCR plan for why): the checkmark region sits partly
# over the panel's semi-transparent background (the blurred game scene
# behind the panel), so its brightness varies with what happens to be
# behind that specific cell — occasionally bright enough to cross the
# threshold with no checkmark actually present. The book-icon region sits
# entirely on the opaque label strip, so its background is always the same
# dark color regardless of position, giving a much wider found/not-found
# brightness gap (validated against a real hand-verified 47-item ground
# truth list: 0 false positives, 0 false negatives, vs. 3 false positives
# with the checkmark region).
BOOK_ICON_REL_X = (9, 24)
BOOK_ICON_REL_Y = (102, 117)
# Mean R+G+B per pixel in that sub-region. Found cells cluster ~500-590;
# not-found cells (including the checkmark-region false positives) cluster
# ~50-152 — 300 sits in the middle of a wide, clean gap. A brightness value,
# not a spatial measurement — does NOT scale with resolution.
OWNED_ICON_BRIGHTNESS_THRESHOLD = 300.0

SCROLLBAR_X = 1970
SCROLLBAR_TRACK_TOP = GRID_ORIGIN_Y_TOP  # thumb top flush here when scrolled to top
SCROLLBAR_TRACK_BOTTOM = 1118  # thumb bottom flush here when scrolled to bottom
SCROLLBAR_PIN_TOLERANCE = 8  # px, at REFERENCE_WIDTH x REFERENCE_HEIGHT

# Small search-window margins used by find_panel()'s border check (see
# screenshot_reader.py:_has_border_near) -- pulled out as named, scaled
# constants rather than inline literals so they scale consistently with
# everything else instead of silently staying reference-resolution-sized.
BORDER_CHECK_WINDOW_X = (-1, 6)
BORDER_CHECK_WINDOW_Y = (10, 30)


@dataclass(frozen=True)
class GridGeometry:
    """Every pixel-position constant above, scaled to one actual
    screenshot's dimensions. Built once per image via geometry_for() and
    threaded through the rest of the vision module instead of reading the
    bare module constants directly."""

    origin_x: float
    origin_y_top: float
    origin_y_bottom: float
    cell_pitch_x: float
    cell_pitch_y: float
    scrollbar_x: float
    scrollbar_track_top: float
    scrollbar_track_bottom: float
    scrollbar_pin_tolerance: float
    book_icon_rel_x: tuple[float, float]
    book_icon_rel_y: tuple[float, float]
    border_check_window_x: tuple[float, float]
    border_check_window_y: tuple[float, float]


def compute_scale(width: int, height: int) -> tuple[float, float]:
    return width / REFERENCE_WIDTH, height / REFERENCE_HEIGHT


def is_plausible_aspect_ratio(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return False
    reference_ratio = REFERENCE_WIDTH / REFERENCE_HEIGHT
    actual_ratio = width / height
    return abs(actual_ratio - reference_ratio) / reference_ratio <= ASPECT_RATIO_TOLERANCE


def geometry_for(width: int, height: int) -> GridGeometry:
    sx, sy = compute_scale(width, height)
    return GridGeometry(
        origin_x=GRID_ORIGIN_X * sx,
        origin_y_top=GRID_ORIGIN_Y_TOP * sy,
        origin_y_bottom=GRID_ORIGIN_Y_BOTTOM * sy,
        cell_pitch_x=CELL_PITCH * sx,
        cell_pitch_y=CELL_PITCH * sy,
        scrollbar_x=SCROLLBAR_X * sx,
        scrollbar_track_top=SCROLLBAR_TRACK_TOP * sy,
        scrollbar_track_bottom=SCROLLBAR_TRACK_BOTTOM * sy,
        scrollbar_pin_tolerance=SCROLLBAR_PIN_TOLERANCE * sy,
        book_icon_rel_x=(BOOK_ICON_REL_X[0] * sx, BOOK_ICON_REL_X[1] * sx),
        book_icon_rel_y=(BOOK_ICON_REL_Y[0] * sy, BOOK_ICON_REL_Y[1] * sy),
        border_check_window_x=(BORDER_CHECK_WINDOW_X[0] * sx, BORDER_CHECK_WINDOW_X[1] * sx),
        border_check_window_y=(BORDER_CHECK_WINDOW_Y[0] * sy, BORDER_CHECK_WINDOW_Y[1] * sy),
    )


def blueprint_id_for_position(row: int, col: int) -> int | None:
    """row/col are 1-indexed logical grid positions. Returns the blueprint id
    at that position, or None if out of range (e.g. row 9's columns 4-10,
    since 83 isn't a multiple of COLUMNS_PER_ROW)."""
    if not (1 <= row <= TOTAL_ROWS and 1 <= col <= COLUMNS_PER_ROW):
        return None
    blueprint_id = (row - 1) * COLUMNS_PER_ROW + col
    return blueprint_id if blueprint_id <= TOTAL_BLUEPRINTS else None


def visible_rows_for_scroll(pinned_top: bool) -> range:
    """Which 1-indexed logical rows are visible in a screenshot scrolled fully
    to the top vs. fully to the bottom, given a fixed ROWS_PER_VIEWPORT-tall
    viewport."""
    if pinned_top:
        return range(1, ROWS_PER_VIEWPORT + 1)
    start = TOTAL_ROWS - ROWS_PER_VIEWPORT + 1
    return range(start, TOTAL_ROWS + 1)


def readable_rows_for_scroll(pinned_top: bool) -> range:
    """Like visible_rows_for_scroll, but excludes the one row-slot at the
    viewport's outer edge — confirmed empirically against the reference
    screenshots that checkmark reads there are unreliable (that row is
    partly covered by the panel's own header chrome when pinned to the top,
    or clipped above the panel's rounded top edge when pinned to the
    bottom). The excluded edge is always covered by the *other* screenshot
    in a top+bottom pair instead, so nothing is lost — read_grid() uses this
    to decide which rows to actually report."""
    rows = visible_rows_for_scroll(pinned_top)
    if pinned_top:
        return range(rows.start, rows.stop - 1)  # drop the last (bottom-clipped) row
    return range(rows.start + 1, rows.stop)  # drop the first (top-clipped) row


def cell_origin(
    visible_row_index: int, col: int, pinned_top: bool, geometry: GridGeometry
) -> tuple[float, float]:
    """visible_row_index is 0-based (0 = topmost row-slot in the viewport);
    col is 1-indexed. Returns the cell's (x, y) top-left pixel origin. Uses
    whichever of the two independently-calibrated row origins matches this
    screenshot's scroll direction."""
    origin_y = geometry.origin_y_top if pinned_top else geometry.origin_y_bottom
    x = geometry.origin_x + (col - 1) * geometry.cell_pitch_x
    y = origin_y + visible_row_index * geometry.cell_pitch_y
    return x, y
