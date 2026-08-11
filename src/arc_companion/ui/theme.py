"""Single source of truth for colors shared across UI widgets -- so a future
visual pass can change one constant here (e.g. the OWNED color) and have it
apply everywhere it appears, instead of hunting down duplicated hex values.
"""

from arc_companion.domain.friends import Highlight
from arc_companion.domain.status import BlueprintStatus

# ---- General UI chrome ------------------------------------------------------
# Not tied to blueprint status -- used across the action bar, dialogs, and
# the tooltip popup. Pulled together during a pre-launch polish pass from
# hex literals that had been duplicated (or near-duplicated) inline across
# action_bar.py, main_window.py, manage_friends_dialog.py, scan_dialog.py,
# settings_dialog.py, tooltip.py, and blueprint_grid.py's icon placeholder.
# Defined before STATUS_COLORS/HIGHLIGHT_COLORS below since one of them
# (SUCCESS_COLOR) is reused there.

# "Connected"/synced status text (ActionBar's storage label, a successful
# sync) -- also HIGHLIGHT_COLORS' green below, one named constant both
# reference rather than two copies of the same literal.
SUCCESS_COLOR = "#30EF85"
# Lighter green for one-off transient confirmations (a completed Steam link,
# "Added N friend(s).", "Cloud data deleted.") -- a distinct shade from
# SUCCESS_COLOR above, not a typo; kept separate on purpose since merging
# them wasn't asked for, just centralizing the existing values.
SUCCESS_COLOR_LIGHT = "#81C784"
# Transient failure/error status text (sync failed, scan validation failed,
# delete failed) -- appears across ActionBar, ScanDialog, ManageFriendsDialog,
# and SettingsDialog.
ERROR_COLOR = "#E57373"
# ScanDialog's Expedition-regression caution text -- the one caution-toned
# (not error, not success) status color in the app.
WARNING_COLOR = "#FFB74D"

# Secondary/dismissive buttons -- Cancel, Back, Remove, Delete My Data. Some
# call sites pair this with NEUTRAL_BUTTON_BORDER_COLOR (border_width=1) and
# some don't; that distinction is preserved per call site, only the color
# values themselves are centralized here.
NEUTRAL_BUTTON_COLOR = "#615F5D"
NEUTRAL_BUTTON_BORDER_COLOR = "#7A756F"

# ActionBar's "dirty" (unsaved changes pending) Sync button -- matches the
# app's own CTk default color theme ("blue", set in main_window.py), used
# here as an explicit override so this one button stays lit even if
# CTkButton's usual default styling changes elsewhere.
ACCENT_COLOR = "#1F6AA5"

# ScanDialog's "Apply as Expedition Reset" button -- the one destructive
# (not just dismissive) action in the app, styled apart from
# NEUTRAL_BUTTON_COLOR so it doesn't read as a routine Cancel/Back.
DESTRUCTIVE_COLOR = "#C62828"
DESTRUCTIVE_HOVER_COLOR = "#B71C1C"

# BlueprintCard's fallback box for a blueprint whose icon image is missing on
# disk -- a close but deliberately distinct blue from ACCENT_COLOR above (not
# yet unified; flagged as a candidate to merge in a future visual pass rather
# than done silently here).
PLACEHOLDER_ICON_COLOR = "#1F538D"

# ActionBar's own top border, separating it from the grid above.
ACTION_BAR_BORDER_COLOR = "#2A2A2A"

# The custom hover tooltip popup (ui/tooltip.py) -- CTk has no built-in
# tooltip widget, so this is a plain tkinter.Toplevel/Label, styled to match
# the rest of the dark theme rather than tkinter's own light-theme default.
TOOLTIP_BG_COLOR = "#1F1F1F"
TOOLTIP_FG_COLOR = "#EEEEEE"

# ---- Blueprint status --------------------------------------------------------

# (label, fg_color, hover_color) per status -- used by both the blueprint
# card's status button and the new per-tile friend-status dots. UNOWNED's
# fg_color was lightened from an earlier #333333 per designer feedback -- it
# blended into the card/icon background at that darkness.
STATUS_COLORS: dict[BlueprintStatus, tuple[str, str, str]] = {
    BlueprintStatus.UNOWNED: ("Unowned", "#818181", "#A7A7A7"),
    BlueprintStatus.OWNED: ("Owned", "#5951BB", "#7069C7"),
    BlueprintStatus.WANT: ("Want", "#30EF85", "#8DEEB9"),
    BlueprintStatus.HAVE: ("Have", "#81F2EB", "#B8F0EC"),
}

# (border_width, border_color) per highlight tier. Green = "a friend has one
# I might want", cyan = "I could give mine away" -- chosen distinct from the
# STATUS_COLORS hexes above so a highlighted border never reads as a status.
# NONE gets a visible thin light-grey outline (not invisible/width=0) per
# designer feedback -- neutral tiles should still read as tiles.
HIGHLIGHT_COLORS: dict[Highlight, tuple[int, str]] = {
    Highlight.NONE: (1, "#4A4A4A"),
    Highlight.THIN_GREEN: (1, SUCCESS_COLOR),
    Highlight.THICK_GREEN: (3, SUCCESS_COLOR),
    Highlight.THIN_CYAN: (1, "#81F2EB"),
    Highlight.THICK_CYAN: (3, "#81F2EB"),
}
