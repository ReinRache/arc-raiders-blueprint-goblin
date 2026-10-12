"""Draws the scanner's view of a collection screenshot so calibration (and the
hand-edited layout files) can be checked with your own eyes.

For every cell the scanner would read it draws the cell rectangle, the cell's
1-based reading-order INDEX (the same position as the line number in
data/layouts/<category>.csv, minus the header) and colors it by what the
scanner decided: green = found, red = empty. A scroll position and panel spec
decide which cells exist; the layout (optional) adds the item id each cell is
tied to, so "cell 14 is Cerulean" can be read straight off the picture.

Usage (from the repo root):

    python tools/debug_grid_overlay.py shot_top.png  --top    --panel legacy_blueprint
    python tools/debug_grid_overlay.py shot_bot.png  --bottom --panel legacy_blueprint
    python tools/debug_grid_overlay.py shot.png --top --panel stencil --layout stencil

Writes <name>_overlay.png next to the screenshot (or --out PATH). Calibration
is a data edit: adjust the panel's entry in data/layouts/geometry.json and
re-run until the rectangles sit on the real cells and found/empty is right.
If the picture looks wrong, trust the picture over the numbers -- this tool
exists because proportional-pixel reasoning is easy to get subtly wrong.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arc_companion.data.layouts import layout_path, load_layout  # noqa: E402
from arc_companion.vision import screenshot_reader as sr  # noqa: E402
from arc_companion.vision.grid_calibration import (  # noqa: E402
    PanelSpec,
    cell_origin,
    geometry_for,
    load_panel_specs,
    readable_rows_for_scroll,
    total_rows,
    visible_rows_for_scroll,
)

_FOUND = (60, 220, 90)
_EMPTY = (230, 70, 70)
_EDGE = (255, 200, 0)  # rows that are visible but not read (clipped edge row)


def render_overlay(
    image: np.ndarray, spec: PanelSpec, layout: Sequence[int], pinned_top: bool
) -> tuple[Image.Image, dict[int, bool]]:
    """Returns (annotated image, {cell_index: found}) for the cells the
    scanner reads in this screenshot. cell_index is 1-based reading order."""
    height, width = image.shape[:2]
    geometry = sr.refine_geometry(image, geometry_for(width, height, spec), pinned_top)
    rows_total = total_rows(len(layout), spec.columns)
    all_rows = visible_rows_for_scroll(pinned_top, rows_total, spec.rows_per_viewport)
    readable = set(readable_rows_for_scroll(pinned_top, rows_total, spec.rows_per_viewport))

    canvas = Image.fromarray(image).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    results: dict[int, bool] = {}
    for visible_row_index, logical_row in enumerate(all_rows):
        for col in range(1, spec.columns + 1):
            index = (logical_row - 1) * spec.columns + (col - 1)  # 0-based
            if index >= len(layout):
                continue
            x, y = cell_origin(visible_row_index, col, pinned_top, geometry)
            pitch_x, pitch_y = geometry.cell_pitch_x, geometry.cell_pitch_y
            if logical_row in readable:
                found = sr._is_owned_icon_present(image, geometry, x, y, spec.owned_brightness_threshold)
                results[index + 1] = found
                color = _FOUND if found else _EMPTY
                # the small box actually sampled for the found/empty decision
                bx0, bx1 = x + geometry.book_icon_rel_x[0], x + geometry.book_icon_rel_x[1]
                by0, by1 = y + geometry.book_icon_rel_y[0], y + geometry.book_icon_rel_y[1]
                draw.rectangle([bx0, by0, bx1, by1], outline=color, width=2)
            else:
                color = _EDGE
            draw.rectangle([x, y, x + pitch_x, y + pitch_y], outline=color, width=2)
            label = f"{index + 1}" + (f" #{layout[index]}" if layout else "")
            draw.text((x + 6, y + 4), label, fill=color)
    return canvas, results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("screenshot", type=Path)
    scroll = parser.add_mutually_exclusive_group(required=True)
    scroll.add_argument("--top", action="store_true", help="screenshot is scrolled fully to the top")
    scroll.add_argument("--bottom", action="store_true", help="screenshot is scrolled fully to the bottom")
    parser.add_argument("--panel", default="legacy_blueprint", help="entry name in data/layouts/geometry.json")
    parser.add_argument("--layout", help="category whose data/layouts/<category>.csv gives cell->item ids")
    parser.add_argument("--cells", type=int, help="number of cells, if no --layout (default: use legacy 83)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    specs = load_panel_specs()
    if args.panel not in specs:
        sys.exit(f"unknown panel {args.panel!r}; geometry.json has: {', '.join(specs)}")
    spec = specs[args.panel]
    if args.layout:
        layout = load_layout(args.layout)
    else:
        layout = list(range(1, (args.cells or 83) + 1))

    image = sr.load_image(args.screenshot)
    pinned_top = args.top
    print(f"panel detected: {sr.find_panel(image, spec)}   scrollbar pinned {'top' if pinned_top else 'bottom'}: "
          f"{sr.is_pinned_top(image, spec) if pinned_top else sr.is_pinned_bottom(image, spec)}")
    overlay, results = render_overlay(image, spec, layout, pinned_top)
    found = sorted(i for i, f in results.items() if f)
    print(f"read {len(results)} cells, {len(found)} found: {found}")
    out = args.out or args.screenshot.with_name(args.screenshot.stem + "_overlay.png")
    overlay.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
