"""Pixel geometry for the in-game collection panels, calibrated at a
reference resolution and scaled proportionally to whatever resolution an
actual screenshot turns out to be (see geometry_for()).

The numbers live in data/layouts/geometry.json as PanelSpec entries -- not
here -- because the game reshuffles its collection screens: a new layout is a
data edit, not a code change. Which item sits in which cell is data too
(data/layouts/<category>.csv, see data/layouts.py), so a grid's size is just
the length of its layout list, never a constant.

Confirmed empirically, not assumed, that panels scale this way: real
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

Functions below default to LEGACY_SPEC/LEGACY_LAYOUT -- the original single
83-item Blueprints panel every regression fixture was calibrated against --
so existing callers are unchanged; the app passes real specs and layouts.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from arc_companion.paths import resource_root

GEOMETRY_JSON = resource_root() / "data" / "layouts" / "geometry.json"


@dataclass(frozen=True)
class PanelSpec:
    """Calibration for one in-game collection panel. Every spatial value is
    in pixels at reference_width x reference_height and scales proportionally
    to the actual screenshot (see geometry_for). The notes that used to sit
    on each module constant (why top and bottom origins differ, why the book
    icon rather than the checkmark, how the threshold was chosen) live on the
    fields below."""

    label: str
    enabled: bool
    reference_width: int
    reference_height: int
    # How far a screenshot's aspect ratio may drift from the reference's
    # before proportional scaling can't be trusted -- covers the ~0.1% jitter
    # measured between 1920x1080, 2556x1439-class and 2560x1440, but not an
    # unverified shape such as ultrawide.
    aspect_ratio_tolerance: float
    origin_x: float
    cell_pitch: float
    # The scrolled-to-top and scrolled-to-bottom views do NOT share one
    # origin: bottom-anchored scrolling doesn't land on a clean multiple of
    # the pitch from the top (a shared-origin assumption was once off by
    # ~130px and silently misread most of a bottom screenshot). Each is
    # calibrated independently. origin_y_bottom is the *slot 0* origin of the
    # first visible row-slot, which is mostly clipped off-screen -- expected.
    origin_y_top: float
    origin_y_bottom: float
    columns: int
    rows_per_viewport: int  # visible row-slots per screenshot; the last is often clipped
    # A found cell shows a small "book" icon bottom-left on the cell's opaque
    # name strip; an unfound slot is completely empty. Far more reliable than
    # the checkmark badge near the top-right, whose region sits partly over
    # the semi-transparent panel and so varies with the blurred scene behind
    # it (validated against a hand-checked 47-item ground truth: 0 false
    # positives/negatives, vs 3 false positives with the checkmark region).
    book_icon_rel_x: tuple[float, float]
    book_icon_rel_y: tuple[float, float]
    # Mean R+G+B per pixel in that region. Found cells cluster ~500-590,
    # not-found ~50-152; 300 sits mid-gap. A brightness value, not a spatial
    # measurement -- does NOT scale with resolution.
    owned_brightness_threshold: float
    scrollbar_x: float
    scrollbar_track_top: float  # thumb top flush here when scrolled to top
    scrollbar_track_bottom: float  # thumb bottom flush here when scrolled to bottom
    scrollbar_pin_tolerance: float  # px at reference resolution
    # Search-window margins for find_panel()'s border check, scaled like
    # everything else rather than left as reference-sized literals.
    border_check_window_x: tuple[float, float]
    border_check_window_y: tuple[float, float]


def load_panel_specs(path: Path = GEOMETRY_JSON) -> dict[str, PanelSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    specs: dict[str, PanelSpec] = {}
    for key, entry in raw.items():
        if key.startswith("_"):
            continue  # comment keys
        specs[key] = PanelSpec(
            label=entry["label"],
            enabled=bool(entry.get("enabled", True)),
            reference_width=entry["reference_width"],
            reference_height=entry["reference_height"],
            aspect_ratio_tolerance=entry["aspect_ratio_tolerance"],
            origin_x=entry["origin_x"],
            cell_pitch=entry["cell_pitch"],
            origin_y_top=entry["origin_y_top"],
            origin_y_bottom=entry["origin_y_bottom"],
            columns=entry["columns"],
            rows_per_viewport=entry["rows_per_viewport"],
            book_icon_rel_x=tuple(entry["book_icon_rel_x"]),
            book_icon_rel_y=tuple(entry["book_icon_rel_y"]),
            owned_brightness_threshold=entry["owned_brightness_threshold"],
            scrollbar_x=entry["scrollbar_x"],
            scrollbar_track_top=entry["scrollbar_track_top"],
            scrollbar_track_bottom=entry["scrollbar_track_bottom"],
            scrollbar_pin_tolerance=entry["scrollbar_pin_tolerance"],
            border_check_window_x=tuple(entry["border_check_window_x"]),
            border_check_window_y=tuple(entry["border_check_window_y"]),
        )
    return specs


# The original single Blueprints panel (83 items, 10 columns).
LEGACY_SPEC: PanelSpec = load_panel_specs()["legacy_blueprint"]
LEGACY_LAYOUT: tuple[int, ...] = tuple(range(1, 84))

# Back-compat names for the legacy panel (existing tests and notes use them).
REFERENCE_WIDTH = LEGACY_SPEC.reference_width
REFERENCE_HEIGHT = LEGACY_SPEC.reference_height
ASPECT_RATIO_TOLERANCE = LEGACY_SPEC.aspect_ratio_tolerance
COLUMNS_PER_ROW = LEGACY_SPEC.columns
ROWS_PER_VIEWPORT = LEGACY_SPEC.rows_per_viewport
TOTAL_BLUEPRINTS = len(LEGACY_LAYOUT)
OWNED_ICON_BRIGHTNESS_THRESHOLD = LEGACY_SPEC.owned_brightness_threshold
SCROLLBAR_X = LEGACY_SPEC.scrollbar_x
SCROLLBAR_TRACK_TOP = LEGACY_SPEC.scrollbar_track_top
SCROLLBAR_TRACK_BOTTOM = LEGACY_SPEC.scrollbar_track_bottom


def total_rows(cell_count: int, columns: int) -> int:
    """Rows needed for `cell_count` items -- a grid's size is how many items
    its layout lists, never a constant."""
    return -(-cell_count // columns)


TOTAL_ROWS = total_rows(TOTAL_BLUEPRINTS, COLUMNS_PER_ROW)  # 9 for the legacy panel


@dataclass(frozen=True)
class GridGeometry:
    """Every pixel-position value of a PanelSpec, scaled to one actual
    screenshot's dimensions. Built once per image via geometry_for() and
    threaded through the rest of the vision module."""

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


def compute_scale(width: int, height: int, spec: PanelSpec = LEGACY_SPEC) -> tuple[float, float]:
    return width / spec.reference_width, height / spec.reference_height


def is_plausible_aspect_ratio(width: int, height: int, spec: PanelSpec = LEGACY_SPEC) -> bool:
    if width <= 0 or height <= 0:
        return False
    reference_ratio = spec.reference_width / spec.reference_height
    actual_ratio = width / height
    return abs(actual_ratio - reference_ratio) / reference_ratio <= spec.aspect_ratio_tolerance


def geometry_for(width: int, height: int, spec: PanelSpec = LEGACY_SPEC) -> GridGeometry:
    sx, sy = compute_scale(width, height, spec)
    return GridGeometry(
        origin_x=spec.origin_x * sx,
        origin_y_top=spec.origin_y_top * sy,
        origin_y_bottom=spec.origin_y_bottom * sy,
        cell_pitch_x=spec.cell_pitch * sx,
        cell_pitch_y=spec.cell_pitch * sy,
        scrollbar_x=spec.scrollbar_x * sx,
        scrollbar_track_top=spec.scrollbar_track_top * sy,
        scrollbar_track_bottom=spec.scrollbar_track_bottom * sy,
        scrollbar_pin_tolerance=spec.scrollbar_pin_tolerance * sy,
        book_icon_rel_x=(spec.book_icon_rel_x[0] * sx, spec.book_icon_rel_x[1] * sx),
        book_icon_rel_y=(spec.book_icon_rel_y[0] * sy, spec.book_icon_rel_y[1] * sy),
        border_check_window_x=(spec.border_check_window_x[0] * sx, spec.border_check_window_x[1] * sx),
        border_check_window_y=(spec.border_check_window_y[0] * sy, spec.border_check_window_y[1] * sy),
    )


def item_id_for_position(layout: Sequence[int], row: int, col: int, columns: int) -> int | None:
    """row/col are 1-indexed logical grid positions. Returns the item id at
    that position per the layout (items in reading order), or None past the
    end of the list (e.g. the last row's unused cells) or off the grid."""
    if row < 1 or not 1 <= col <= columns:
        return None
    index = (row - 1) * columns + (col - 1)
    return layout[index] if index < len(layout) else None


def blueprint_id_for_position(row: int, col: int) -> int | None:
    """Legacy-panel wrapper: the original (row-1)*10+col positions of the 83
    blueprints (83 isn't a multiple of 10, so row 9 has only 3 cells)."""
    return item_id_for_position(LEGACY_LAYOUT, row, col, LEGACY_SPEC.columns)


def visible_rows_for_scroll(
    pinned_top: bool, rows_total: int = TOTAL_ROWS, rows_per_viewport: int = ROWS_PER_VIEWPORT
) -> range:
    """Which 1-indexed logical rows are visible in a screenshot scrolled fully
    to the top vs. fully to the bottom, given a fixed-height viewport. (A grid
    no taller than the viewport shows all its rows either way.)"""
    visible = min(rows_per_viewport, rows_total)
    if pinned_top:
        return range(1, visible + 1)
    return range(rows_total - visible + 1, rows_total + 1)


def readable_rows_for_scroll(
    pinned_top: bool, rows_total: int = TOTAL_ROWS, rows_per_viewport: int = ROWS_PER_VIEWPORT
) -> range:
    """Like visible_rows_for_scroll, but excludes the one row-slot at the
    viewport's outer edge — confirmed empirically against the reference
    screenshots that checkmark reads there are unreliable (that row is
    partly covered by the panel's own header chrome when pinned to the top,
    or clipped above the panel's rounded top edge when pinned to the
    bottom). The excluded edge is always covered by the *other* screenshot
    in a top+bottom pair instead, so nothing is lost — read_grid() uses this
    to decide which rows to actually report."""
    rows = visible_rows_for_scroll(pinned_top, rows_total, rows_per_viewport)
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
