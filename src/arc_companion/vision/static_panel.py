"""Scanner for the Frozen Trail collection screens.

Since the update each collection tab (Blueprints / Stencils / Designs) is ONE
non-scrolling grid, so a single full-window screenshot per tab is enough --
no scrollbar, no top/bottom pair, no stitching. Everything spatial lives in
data/layouts/geometry.json (StaticPanelSpec entries, in pixels at
reference_width x reference_height, scaled proportionally to the screenshot);
which item sits in which cell lives in data/layouts/<category>.csv. A cell's
position is just its index in that list, so a game update that inserts an
item mid-grid is a data edit, not a code change.

Detection (calibrated against real screenshots with hand-listed ground truth
-- 205 cells across the three tabs, 0 misclassified):
  * A tile is FOUND when a small box at its lower-left (the "book" /
    "stencil" / "design" glyph) is bright. On Blueprints and Designs an
    unfound tile is completely empty there (brightness ~10-45 vs ~295-330
    found); on Stencils an unfound tile shows a dim version of the same glyph
    (~410 vs ~665 found). Brightness is mean R+G+B per pixel.
  * The ACTIVE TAB is identified by the bright pill outline around its label
    (~684 vs ~9 for inactive tabs). Essential: Blueprints and Designs have
    identical geometry, so without this a Designs screenshot scanned as
    Blueprints would be silently misread.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from arc_companion.vision.grid_calibration import GEOMETRY_JSON


@dataclass(frozen=True)
class StaticPanelSpec:
    category: str
    label: str
    enabled: bool
    reference_width: int
    reference_height: int
    aspect_ratio_tolerance: float
    columns: int
    # Center of the first tile's found-icon, and the distance to the next
    # tile across / down, in reference pixels. Any tile is
    # first + (col * pitch_x, row * pitch_y).
    first_icon_center: tuple[float, float]
    pitch_x: float
    pitch_y: float
    icon_half_size: float  # half the side of the square sampled at each icon
    found_brightness_threshold: float
    # Pill-outline probe segments (x0, y0, x1, y1) per tab, in reference px.
    tab_probes: dict[str, tuple[float, float, float, float]]
    tab_probe_brightness_threshold: float


def load_static_specs(path: Path = GEOMETRY_JSON) -> dict[str, StaticPanelSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    specs: dict[str, StaticPanelSpec] = {}
    for key, entry in raw.items():
        if key.startswith("_") or entry.get("kind") != "static":
            continue
        specs[key] = StaticPanelSpec(
            category=key,
            label=entry["label"],
            enabled=bool(entry.get("enabled", True)),
            reference_width=entry["reference_width"],
            reference_height=entry["reference_height"],
            aspect_ratio_tolerance=entry["aspect_ratio_tolerance"],
            columns=entry["columns"],
            first_icon_center=tuple(entry["first_icon_center"]),
            pitch_x=entry["pitch_x"],
            pitch_y=entry["pitch_y"],
            icon_half_size=entry["icon_half_size"],
            found_brightness_threshold=entry["found_brightness_threshold"],
            tab_probes={tab: tuple(box) for tab, box in entry["tab_probes"].items()},
            tab_probe_brightness_threshold=entry["tab_probe_brightness_threshold"],
        )
    return specs


def is_plausible_aspect_ratio(width: int, height: int, spec: StaticPanelSpec) -> bool:
    if width <= 0 or height <= 0:
        return False
    reference = spec.reference_width / spec.reference_height
    return abs(width / height - reference) / reference <= spec.aspect_ratio_tolerance


def _box_brightness(image: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> float | None:
    """Mean R+G+B per pixel of a box (None if it falls outside the image)."""
    height, width = image.shape[:2]
    left, right = round(x0), max(round(x1), round(x0) + 1)
    top, bottom = round(y0), max(round(y1), round(y0) + 1)
    if left < 0 or top < 0 or right > width or bottom > height:
        return None
    return float(image[top:bottom, left:right].astype(float).sum(axis=2).mean())


def active_tab(image: np.ndarray, spec: StaticPanelSpec) -> str | None:
    """Which collection tab this screenshot shows, from the bright pill
    outline around its label -- or None if no tab (or several) read as
    active, i.e. this isn't a full-window Collections screenshot."""
    height, width = image.shape[:2]
    sx, sy = width / spec.reference_width, height / spec.reference_height
    lit = []
    for tab, (x0, y0, x1, y1) in spec.tab_probes.items():
        brightness = _box_brightness(image, x0 * sx, y0 * sy, x1 * sx, y1 * sy)
        if brightness is not None and brightness > spec.tab_probe_brightness_threshold:
            lit.append(tab)
    return lit[0] if len(lit) == 1 else None


def cell_center(index: int, spec: StaticPanelSpec) -> tuple[float, float]:
    """Reference-pixel center of the found-icon of the cell at 0-based
    reading-order `index`."""
    row, col = divmod(index, spec.columns)
    return (
        spec.first_icon_center[0] + col * spec.pitch_x,
        spec.first_icon_center[1] + row * spec.pitch_y,
    )


def read_static_grid(image: np.ndarray, spec: StaticPanelSpec, layout: Sequence[int]) -> dict[int, bool]:
    """{item_id: found} for every cell in the layout. Cells that fall outside
    the image read as not found."""
    height, width = image.shape[:2]
    sx, sy = width / spec.reference_width, height / spec.reference_height
    half_x, half_y = spec.icon_half_size * sx, spec.icon_half_size * sy
    results: dict[int, bool] = {}
    for index, item_id in enumerate(layout):
        cx, cy = cell_center(index, spec)
        brightness = _box_brightness(image, cx * sx - half_x, cy * sy - half_y, cx * sx + half_x, cy * sy + half_y)
        results[item_id] = brightness is not None and brightness > spec.found_brightness_threshold
    return results
