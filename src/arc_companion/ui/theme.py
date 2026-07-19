"""Single source of truth for colors shared across UI widgets -- so a future
visual pass can change one constant here (e.g. the OWNED color) and have it
apply everywhere it appears, instead of hunting down duplicated hex values.
"""

from arc_companion.domain.friends import Highlight
from arc_companion.domain.status import BlueprintStatus

# (label, fg_color, hover_color) per status -- used by both the blueprint
# card's status button and the new per-tile friend-status dots. UNOWNED's
# fg_color was lightened from an earlier #333333 per designer feedback -- it
# blended into the card/icon background at that darkness.
STATUS_COLORS: dict[BlueprintStatus, tuple[str, str, str]] = {
    BlueprintStatus.UNOWNED: ("Unowned", "#5C5C5C", "#6E6E6E"),
    BlueprintStatus.OWNED: ("Owned", "#4932CC", "#796ACE"),
    BlueprintStatus.WANT: ("Want", "#1F8535", "#589666"),
    BlueprintStatus.HAVE: ("Have", "#22A8C0", "#8BB8C0"),
}

# (border_width, border_color) per highlight tier. Green = "a friend has one
# I might want", cyan = "I could give mine away" -- chosen distinct from the
# STATUS_COLORS hexes above so a highlighted border never reads as a status.
# NONE gets a visible thin light-grey outline (not invisible/width=0) per
# designer feedback -- neutral tiles should still read as tiles.
HIGHLIGHT_COLORS: dict[Highlight, tuple[int, str]] = {
    Highlight.NONE: (1, "#4A4A4A"),
    Highlight.THIN_GREEN: (1, "#4CAF50"),
    Highlight.THICK_GREEN: (3, "#4CAF50"),
    Highlight.THIN_CYAN: (1, "#26C6DA"),
    Highlight.THICK_CYAN: (3, "#26C6DA"),
}
