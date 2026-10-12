import importlib.util
from pathlib import Path

from arc_companion.vision import screenshot_reader as sr
from arc_companion.vision.grid_calibration import LEGACY_LAYOUT, LEGACY_SPEC

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "debug_grid_overlay.py"
_FIXTURE = Path(__file__).parent / "fixtures" / "blueprints_panel_top.png"


def _load_tool():
    spec = importlib.util.spec_from_file_location("debug_grid_overlay", _TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overlay_agrees_with_the_scanner_on_which_cells_are_found():
    # The overlay is only useful for calibration if it shows exactly what the
    # scanner decided, so it must not have its own copy of the logic.
    tool = _load_tool()
    image = sr.load_image(_FIXTURE)
    overlay, results = tool.render_overlay(image, LEGACY_SPEC, LEGACY_LAYOUT, pinned_top=True)
    scanner = sr.read_grid(image, pinned_top=True)
    assert {LEGACY_LAYOUT[i - 1]: found for i, found in results.items()} == scanner
    assert overlay.size == (image.shape[1], image.shape[0])
