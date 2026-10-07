import tkinter
from collections.abc import Callable
from functools import lru_cache

import customtkinter as ctk
from PIL import Image

from arc_companion.data.blueprints import IMAGES_DIR, Blueprint
from arc_companion.domain.friends import FriendStatusCounts, Highlight, compute_highlight
from arc_companion.domain.status import BlueprintStatus
from arc_companion.ui.theme import HIGHLIGHT_COLORS, PLACEHOLDER_ICON_COLOR, STATUS_COLORS
from arc_companion.ui.tooltip import Tooltip

# Header line shown above the friend-name list in each dot's hover tooltip --
# gives first-time viewers context for what the list of names means, since
# the dot alone (a color + a count) isn't self-explanatory.
_TOOLTIP_HEADERS: dict[BlueprintStatus, str] = {
    BlueprintStatus.UNOWNED: "Unowned By",
    BlueprintStatus.WANT: "Wanted By",
    BlueprintStatus.OWNED: "Owned By",
    BlueprintStatus.HAVE: "Have a Spare",
}

# Which friend-name list a highlighted tile's icon-hover tooltip should show
# -- mirrors compute_highlight()'s own logic (domain/friends.py) so the
# tooltip always explains the *actual* reason a given tile is highlighted,
# not just a plausible-looking one. NONE is deliberately absent -- an
# unhighlighted tile has no recommended trade, so its icon gets no tooltip.
_HIGHLIGHT_TRADE_STATUS: dict[Highlight, BlueprintStatus] = {
    Highlight.THIN_GREEN: BlueprintStatus.HAVE,
    Highlight.THICK_GREEN: BlueprintStatus.HAVE,
    Highlight.THIN_CYAN: BlueprintStatus.UNOWNED,
    Highlight.THICK_CYAN: BlueprintStatus.WANT,
}

_ICON_SIZE = (86, 86)
# The in-game Blueprints panel renders every icon on a distinct colored
# "plate" behind it -- this reproduces that look by tinting the one real
# backdrop asset the wiki scrape already pulled down (previously unused) per
# the tile's status color, instead of needing 4 pre-baked backdrop variants
# per blueprint (332 images). The backdrop is shared/cached once per status
# across every card; only the icon on top differs per blueprint.
_BACKDROP_PATH = IMAGES_DIR / "100px-UI_Blueprint_background.png.webp"
_BACKDROP_TINT_STRENGTH = 0.5  # 0 = original backdrop color, 1 = solid status color
_ICON_INSET_PX = 6  # leaves a visible ring of tinted backdrop around the icon
_CARD_WIDTH = 140
# Grew from 145 to fit the new friends-overlay row (icon + 4 status dots)
# below the existing status button -- provisional pending direct
# winfo_height() re-measurement against a live window (see CLAUDE.md's
# existing notes on why this grid's sizing constants are always measured,
# never just computed).
_CARD_HEIGHT = 172
_CARD_GAP = 8
_NAME_WIDTH = 122
_MAX_COLUMNS = 10
_RESIZE_DEBOUNCE_MS = 150


def _wrap_name(name: str, font: ctk.CTkFont, max_width: int) -> str:
    # Pre-wrap with explicit newlines using the font's actual measured pixel
    # width, rather than relying on CTkLabel's wraplength reflow (which was
    # inconsistent — some names got hard-truncated instead of wrapping) or a
    # guessed characters-per-line budget (bold glyphs vary too much in width
    # for a fixed character count to be reliable).
    words = name.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or font.measure(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def _load_raw_icon(blueprint: Blueprint) -> Image.Image | None:
    if not blueprint.image_path.exists():
        return None
    return Image.open(blueprint.image_path).convert("RGBA")


@lru_cache(maxsize=1)
def _load_backdrop() -> Image.Image | None:
    if not _BACKDROP_PATH.exists():
        return None
    return Image.open(_BACKDROP_PATH).convert("RGBA").resize(_ICON_SIZE)


def _tint_backdrop(backdrop: Image.Image, hex_color: str, strength: float) -> Image.Image:
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    tint = Image.new("RGB", backdrop.size, (r, g, b))
    blended = Image.blend(backdrop.convert("RGB"), tint, strength)
    return Image.merge("RGBA", (*blended.split(), backdrop.split()[3]))


def _compose_status_icon(icon: Image.Image | None, backdrop: Image.Image | None) -> Image.Image | None:
    if backdrop is None:
        return icon.resize(_ICON_SIZE) if icon is not None else None
    composed = backdrop.copy()
    if icon is not None:
        inset_size = (_ICON_SIZE[0] - 2 * _ICON_INSET_PX, _ICON_SIZE[1] - 2 * _ICON_INSET_PX)
        resized = icon.resize(inset_size)
        composed.paste(resized, (_ICON_INSET_PX, _ICON_INSET_PX), resized)
    return composed


class BlueprintCard(ctk.CTkFrame):
    # This card's own children use grid() — fine, since that's a small,
    # isolated 1-column/3-row grid local to this single frame, not shared or
    # renegotiated with sibling cards. The outer BlueprintGrid, which lays out
    # many sibling cards across shared weight=0 columns, uses place() instead
    # — see the comment above BlueprintGrid.render() for why.
    def __init__(
        self,
        master,
        blueprint: Blueprint,
        status: BlueprintStatus,
        on_cycle: Callable[[int], None],
        icon: ctk.CTkImage | None,
        friend_counts: FriendStatusCounts,
        highlight: Highlight,
    ):
        super().__init__(master, width=_CARD_WIDTH, height=_CARD_HEIGHT, corner_radius=6)
        self.grid_propagate(False)
        self.blueprint = blueprint
        self._status = status
        self._friend_counts = friend_counts
        self._highlight = highlight

        # Mirrors the status button: clicking the icon (or its placeholder,
        # when a blueprint has no icon on disk) cycles ownership status the
        # same way clicking the button does -- a bigger, more discoverable
        # click target than the small button alone. cursor="hand2" hints
        # it's clickable the way CTkButton already does natively.
        def _on_icon_click(event: object) -> None:
            on_cycle(self.blueprint.id)

        self.icon_label: ctk.CTkLabel | None = None
        if icon is not None:
            self._icon = icon  # keep a reference alive; Tk drops images with no referrer
            self.icon_label = ctk.CTkLabel(self, image=icon, text="", cursor="hand2")
            self.icon_label.grid(row=0, column=0, padx=5, pady=(4, 2))
            self.icon_label.bind("<Button-1>", _on_icon_click)
            # Only shows while this tile has a highlight border (a
            # recommended trade) -- _icon_tooltip_text returns "" otherwise,
            # and Tooltip already suppresses an empty popup, same as the
            # friend-count dots below.
            Tooltip(self.icon_label, self._icon_tooltip_text)
        else:
            placeholder = ctk.CTkFrame(
                self,
                width=_ICON_SIZE[0],
                height=_ICON_SIZE[1],
                fg_color=PLACEHOLDER_ICON_COLOR,
                corner_radius=4,
                cursor="hand2",
            )
            placeholder.grid_propagate(False)
            placeholder.grid(row=0, column=0, padx=5, pady=(4, 2))
            placeholder.bind("<Button-1>", _on_icon_click)
            Tooltip(placeholder, self._icon_tooltip_text)

        name_font = ctk.CTkFont(size=11, weight="bold")
        self.name_label = ctk.CTkLabel(
            self,
            text=_wrap_name(blueprint.name, name_font, _NAME_WIDTH - 8),
            font=name_font,
            width=_NAME_WIDTH,
            justify="center",
            anchor="center",
        )
        self.name_label.grid(row=1, column=0, padx=5, pady=0, sticky="ew")

        self.status_btn = ctk.CTkButton(
            self,
            text="",
            font=ctk.CTkFont(size=10),
            height=18,
            width=85,
            command=lambda: on_cycle(self.blueprint.id),
        )
        self.status_btn.grid(row=2, column=0, padx=10, pady=(2, 2))

        # Friends overlay row: a small icon + one dot per BlueprintStatus,
        # each showing how many active friends are in that state and, on
        # hover, listing their names.
        friends_row = ctk.CTkFrame(self, fg_color="transparent")
        # padx must clear the card's own corner_radius (6) or the outer
        # icon/dot visually pokes past the rounded corner when this row
        # stretches ("ew") to fill the column width -- confirmed by the
        # designer against a real screenshot at padx=2.
        friends_row.grid(row=3, column=0, padx=8, pady=(0, 3), sticky="ew")
        friends_row.grid_columnconfigure(tuple(range(6)), weight=1)
        # height=18 overrides CTkLabel's default (28px, unrelated to font
        # size) -- left at the default, each label's box was noticeably
        # taller than its glyph needs, and that extra internal padding
        # pushed the row's effective bottom edge into the card's border.
        ctk.CTkLabel(friends_row, text="\U0001F465", font=ctk.CTkFont(size=13), height=18).grid(
            row=0, column=0, padx=(2, 4)
        )
        self._dot_labels: dict[BlueprintStatus, ctk.CTkLabel] = {}
        for i, dot_status in enumerate(BlueprintStatus, start=1):
            _, fg, _ = STATUS_COLORS[dot_status]
            dot = ctk.CTkLabel(friends_row, text="●0", font=ctk.CTkFont(size=13), text_color=fg, height=18)
            dot.grid(row=0, column=i, padx=4)
            Tooltip(dot, (lambda s=dot_status: self._tooltip_text_for(s)))
            self._dot_labels[dot_status] = dot

        self.set_status(status, icon)
        self.set_friend_overlay(friend_counts, highlight)

    def _tooltip_text_for(self, status: BlueprintStatus) -> str:
        names = self._friend_counts.for_status(status)
        if not names:
            return ""  # Tooltip itself suppresses an empty popup -- no names, no header either.
        return "\n".join([_TOOLTIP_HEADERS[status], *names])

    def _icon_tooltip_text(self) -> str:
        # Which friend-name list actually explains *this* tile's highlight
        # border, not just "whichever list happens to be non-empty" --
        # compute_highlight() picks THICK_CYAN over THIN_CYAN when a friend
        # both wants it AND others don't own it, so THIN_CYAN showing here
        # implies counts.want is empty and counts.unowned is the right (and
        # only) list to show, not an arbitrary choice.
        status = _HIGHLIGHT_TRADE_STATUS.get(self._highlight)
        if status is None:
            return ""
        return self._tooltip_text_for(status)

    def set_status(self, status: BlueprintStatus, icon: ctk.CTkImage | None) -> None:
        self._status = status
        text, color, hover = STATUS_COLORS[status]
        self.status_btn.configure(text=text, fg_color=color, hover_color=hover)
        # The backdrop tint behind the icon is per-status too (see
        # _compose_status_icon), so a status change needs a new composited
        # image, not just the button re-styled.
        if icon is not None and self.icon_label is not None:
            self._icon = icon
            self.icon_label.configure(image=icon)

    def set_friend_overlay(self, friend_counts: FriendStatusCounts, highlight: Highlight) -> None:
        self._friend_counts = friend_counts
        self._highlight = highlight
        for dot_status, label in self._dot_labels.items():
            count = len(friend_counts.for_status(dot_status))
            label.configure(text=f"●{count}")
        border_width, border_color = HIGHLIGHT_COLORS[highlight]
        self.configure(border_width=border_width, border_color=border_color)


# Public (no leading underscore): main_window.py uses this to size the
# window itself so the default/minimum widths land on an exact number of
# columns with no leftover slack — see MainWindow's _GRID_OVERHEAD_PX.
CELL_SIZE = _CARD_WIDTH + _CARD_GAP
# Same idea, vertically -- main_window.py's compact-display sizing uses
# this to land on an exact number of visible rows.
ROW_CELL_SIZE = _CARD_HEIGHT + _CARD_GAP


def compute_columns(available_width: int) -> int:
    return max(1, min(_MAX_COLUMNS, available_width // CELL_SIZE))


class BlueprintGrid(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        blueprints: list[Blueprint],
        status_for_id: Callable[[int], BlueprintStatus],
        on_cycle: Callable[[int], None],
        friend_counts_for_id: Callable[[int], FriendStatusCounts],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.blueprints = blueprints
        self.status_for_id = status_for_id
        self.on_cycle = on_cycle
        self.friend_counts_for_id = friend_counts_for_id
        self.cards: dict[int, BlueprintCard] = {}
        self._raw_icon_cache: dict[int, Image.Image | None] = {}
        self._tinted_backdrop_cache: dict[BlueprintStatus, Image.Image | None] = {}
        self._status_icon_cache: dict[tuple[int, BlueprintStatus], ctk.CTkImage | None] = {}
        self._search_query = ""
        self._resize_after_id: str | None = None
        # 0 is not a value compute_columns() can ever return (it's clamped to
        # >= 1), so the very first real <Configure> event below is guaranteed
        # to see a "changed" column count and trigger the first render — see
        # the comment on _on_canvas_configure for why we don't render() here.
        self.columns = 0

        # CTkScrollableFrame places this frame (`self`) *inside* a tkinter.Canvas
        # (`self._parent_canvas`) via create_window — the canvas is the real
        # scrollable viewport (its width already accounts for the scrollbar), and
        # it stretches `self` to match its own width on resize. `self`'s width is
        # therefore a *result* of the canvas's size, not a measurement of
        # available space — binding our resize handler to `self` instead of the
        # canvas made columns shrink based on our own last-rendered width instead
        # of the real viewport (the "chunking down early, wasted space on the
        # right" bug). We bind to the canvas with add="+" rather than `self`,
        # since CTkScrollableFrame's own __init__ already binds "<Configure>" on
        # `self` to keep the canvas's scrollregion in sync with content size —
        # using plain bind() here previously clobbered that binding entirely,
        # which is why the scrollbar/mouse wheel stopped working.
        #
        # We deliberately do NOT call self.render() here. CTkScrollableFrame
        # defaults to a 200px-wide canvas until the real window layout settles
        # (we never pass an explicit width/height), so an eager render() at
        # construction time would try to lay out cards into that placeholder
        # 200px canvas before we have any idea how many columns really fit.
        self._parent_canvas.bind("<Configure>", self._on_canvas_configure, add="+")

    def _set_scaling(self, new_widget_scaling, new_window_scaling) -> None:
        # Fires when CTk's own DPI poll (ScalingTracker) detects this
        # window moved to a different-DPI monitor -- e.g. dragged from a
        # 100%-scaled display onto a 4K one running 150%. Every CTk widget
        # rescales itself automatically from this callback (see
        # CTkBaseClass._set_scaling replaying each widget's last place()
        # call through _apply_argument_scaling), which is why the cards
        # themselves reposition correctly with no code here at all. The
        # scrollable content height set at the end of render() is the one
        # thing that doesn't self-heal that way -- it's a raw
        # tkinter.Frame.configure() call with no CTk wrapper watching it --
        # so without an explicit re-render here it goes stale at whatever
        # was last computed for the old scaling factor. This is also the
        # only reliable trigger for that: _on_canvas_configure only
        # re-renders when compute_columns()'s result actually changes,
        # which a pure DPI change doesn't guarantee (dragging between two
        # same-width, different-DPI monitors can leave the column count
        # unchanged while still needing a rescaled content height).
        #
        # Debounced through the same _resize_after_id timer
        # _on_canvas_configure uses, not called directly -- customtkinter's
        # own DPI poll is supposed to suppress reentrant dimension-change
        # handling while it rescales every widget in the tree
        # (Tk.block_update_dimensions_event / unblock_update_dimensions_
        # event), but that method has a real, confirmed upstream bug: both
        # set the same flag to False, so "block" never actually blocks
        # anything (github.com/TomSchimansky/CustomTkinter/blob/master/
        # customtkinter/windows/ctk_tk.py, still present as of this
        # writing). While a window straddles a monitor boundary, Windows'
        # "which monitor is this on" answer can flip repeatedly as the
        # overlap ratio crosses 50%, and each flip re-triggers a full
        # rescale -- calling render() (an 83-card re-layout) directly from
        # here on every one of those, unthrottled, is exactly the kind of
        # extra work that turns "CTk's own DPI handling is imperfect" into
        # a real, user-visible performance/stability problem. Debouncing
        # collapses a burst of these into a single render() once the
        # window actually settles on one monitor.
        super()._set_scaling(new_widget_scaling, new_window_scaling)
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(_RESIZE_DEBOUNCE_MS, self._on_resize_settled)

    def _on_canvas_configure(self, event) -> None:
        # event.width is real on-screen pixels; CTk's own size constants
        # (_CARD_WIDTH etc.) are pre-scaling logical units it multiplies by a
        # DPI-driven widget-scaling factor at render time. Reverse that here so
        # the column count is computed in the same unit system as the cards,
        # regardless of display scaling.
        available_width = self._reverse_widget_scaling(event.width)
        columns = compute_columns(available_width)
        if columns == self.columns:
            return
        self.columns = columns
        # Debounced so a live window drag (many Configure events in quick
        # succession) only triggers one re-layout once resizing pauses,
        # instead of re-placing all 83 cards on every intermediate width.
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(_RESIZE_DEBOUNCE_MS, self._on_resize_settled)

    def _on_resize_settled(self) -> None:
        self._resize_after_id = None
        self.render()

    def set_search_query(self, query: str) -> None:
        self._search_query = query.lower().strip()
        # New results always start at the top -- the old scroll offset means
        # nothing for a different list (and is what used to strand the view
        # past the end of a shorter filtered list; see _sync_scroll).
        self.render(reset_scroll=True)

    def refresh_status(self, blueprint_id: int) -> None:
        # My own status is itself an input to compute_highlight(), so a
        # status change needs the overlay recomputed too, not just re-styled.
        if blueprint_id in self.cards:
            card = self.cards[blueprint_id]
            status = self.status_for_id(blueprint_id)
            icon = self._get_status_icon(card.blueprint, status)
            card.set_status(status, icon)
            self._refresh_card_overlay(blueprint_id)

    def refresh_friend_overlay(self) -> None:
        for blueprint_id in self.cards:
            self._refresh_card_overlay(blueprint_id)

    def _refresh_card_overlay(self, blueprint_id: int) -> None:
        counts = self.friend_counts_for_id(blueprint_id)
        highlight = compute_highlight(self.status_for_id(blueprint_id), counts)
        self.cards[blueprint_id].set_friend_overlay(counts, highlight)

    def _get_raw_icon(self, blueprint: Blueprint) -> Image.Image | None:
        if blueprint.id not in self._raw_icon_cache:
            self._raw_icon_cache[blueprint.id] = _load_raw_icon(blueprint)
        return self._raw_icon_cache[blueprint.id]

    def _get_tinted_backdrop(self, status: BlueprintStatus) -> Image.Image | None:
        if status not in self._tinted_backdrop_cache:
            backdrop = _load_backdrop()
            _, color, _ = STATUS_COLORS[status]
            self._tinted_backdrop_cache[status] = (
                _tint_backdrop(backdrop, color, _BACKDROP_TINT_STRENGTH) if backdrop is not None else None
            )
        return self._tinted_backdrop_cache[status]

    def _get_status_icon(self, blueprint: Blueprint, status: BlueprintStatus) -> ctk.CTkImage | None:
        key = (blueprint.id, status)
        if key not in self._status_icon_cache:
            composed = _compose_status_icon(self._get_raw_icon(blueprint), self._get_tinted_backdrop(status))
            self._status_icon_cache[key] = (
                ctk.CTkImage(light_image=composed, dark_image=composed, size=_ICON_SIZE)
                if composed is not None
                else None
            )
        return self._status_icon_cache[key]

    def render(self, reset_scroll: bool = False) -> None:
        # Cards are positioned with place(), not grid(). CTkScrollableFrame's
        # canvas stretches this frame to a *forced* width rather than letting
        # it size itself naturally, and in that situation Tk's grid geometry
        # manager doesn't cleanly release a weight=0 column's width once a
        # card that occupied it is grid_forget()'d and the column count
        # shrinks — re-gridding the same card objects into fewer columns left
        # every column (and thus every card) a fixed handful of pixels
        # narrower than configured (confirmed by direct winfo_width()/
        # grid_bbox() inspection), which showed up as unexplained slack on
        # the right and dropping a column too early. The only reliable fix
        # that kept grid() was destroying and recreating every card on each
        # resize, which was too slow to be usable (~1s per resize step even
        # with icons cached). place() with explicitly computed pixel
        # coordinates has no column-width negotiation to go stale, so
        # existing card widgets can just be repositioned in place — cheap,
        # and immune to this whole class of bug.
        if self.columns < 1:
            # self.columns is still __init__'s 0 sentinel until the first
            # real <Configure> event on the canvas has fired (see __init__
            # for why we don't render() eagerly there). divmod(index, 0)
            # below would crash for anyone who types in the search bar in
            # that brief startup window -- found by inspection while
            # investigating a report of the search bar intermittently
            # emptying the grid with no visible error (a windowed build
            # swallows callback exceptions silently; see
            # MainWindow.report_callback_exception, added at the same time
            # so the *next* occurrence of whatever this doesn't fully
            # explain leaves a real traceback). Safe to just wait:
            # _on_resize_settled's render() call, once the real
            # call, once the real Configure event lands, picks up whatever
            # self._search_query is already set to here, so nothing typed
            # during this window is lost.
            return
        if self._search_query:
            visible = [bp for bp in self.blueprints if self._search_query in bp.name.lower()]
        else:
            visible = self.blueprints
        visible_ids = {bp.id for bp in visible}

        for bp_id, card in self.cards.items():
            if bp_id not in visible_ids:
                card.place_forget()

        cell_w = _CARD_WIDTH + _CARD_GAP
        cell_h = _CARD_HEIGHT + _CARD_GAP
        for index, bp in enumerate(visible):
            if bp.id not in self.cards:
                status = self.status_for_id(bp.id)
                counts = self.friend_counts_for_id(bp.id)
                self.cards[bp.id] = BlueprintCard(
                    self,
                    bp,
                    status,
                    self.on_cycle,
                    self._get_status_icon(bp, status),
                    counts,
                    compute_highlight(status, counts),
                )
            row, col = divmod(index, self.columns)
            # width/height are NOT passed here — CTkBaseClass.place() rejects
            # them outright; card size is fixed once at construction time
            # (width=_CARD_WIDTH/height=_CARD_HEIGHT + grid_propagate(False)).
            self.cards[bp.id].place(
                x=col * cell_w + _CARD_GAP // 2,
                y=row * cell_h + _CARD_GAP // 2,
            )

        # place() doesn't grow its parent to fit placed children the way
        # grid()/pack() do with propagate on, so the scrollable area's total
        # height needs to be set explicitly here for scrolling to reach every
        # row (CTkScrollableFrame keeps the canvas's scrollregion in sync with
        # this frame's own size via its internal <Configure> binding).
        #
        # self.configure(height=...) is NOT the same as tkinter.Frame's own —
        # CTkScrollableFrame overrides configure() and routes "height" to
        # resizing the *canvas viewport* (self._parent_canvas), not this inner
        # content frame. We need the frame's own actual size to grow so the
        # canvas's bbox("all")/scrollregion covers all the placed cards, so
        # bypass the override and set it directly, same as customtkinter's own
        # internals do in a few places (e.g. its bg-color handling) to reach
        # the underlying tkinter.Frame beneath the CTk wrapper.
        total_rows = -(-len(visible) // self.columns) if visible else 0  # ceil div
        content_height = total_rows * cell_h + _CARD_GAP // 2 if total_rows else 1
        # _apply_widget_scaling, not the raw value -- cell_h/_CARD_GAP are
        # logical (pre-DPI-scaling) units, same as the x/y passed to each
        # card's own place() call above. Cards scale themselves correctly
        # because CTkBaseClass.place() runs x/y through this same
        # conversion internally; the raw tkinter.Frame.configure() bypass
        # above doesn't go through any CTk wrapper at all, so it needs the
        # same conversion done explicitly. Without this, the scrollable
        # region is sized in logical pixels while the actual (scaled) cards
        # render larger than that on any display where Windows scaling
        # isn't exactly 100% -- e.g. a 4K monitor at its recommended
        # scaling -- silently cutting off the last row(s) from ever being
        # reachable by scrolling. Confirmed via CTkBaseClass.place()'s own
        # _apply_argument_scaling call, not assumed.
        tkinter.Frame.configure(self, height=self._apply_widget_scaling(content_height))
        self._sync_scroll(reset_scroll)

    def _sync_scroll(self, reset_to_top: bool) -> None:
        # Explicitly re-syncs the canvas's scroll region and view instead of
        # trusting CTkScrollableFrame's own <Configure>-driven update. That
        # update never fires in this case: after a user scrolls down and then
        # filters, the shorter content sits at the top, *outside* the scrolled
        # viewport, and Tk only resizes a canvas window item (and sends it
        # <Configure>) while it's being drawn -- so the frame stays its old
        # height, the scroll region stays stale, and the view stays parked
        # past the end of the content: an empty grid until something nudges
        # the canvas (a different query, a scroll). Reported by a tester as
        # "my first search shows nothing; I have to search twice".
        canvas = self._parent_canvas
        if reset_to_top:
            canvas.yview_moveto(0)  # back in view first, so the frame redraws
        canvas.configure(scrollregion=canvas.bbox("all"))
        content_px = canvas.bbox("all")[3] if canvas.bbox("all") else 0
        viewport_px = canvas.winfo_height()
        top_px = canvas.canvasy(0)
        if content_px <= viewport_px:
            canvas.yview_moveto(0)
        elif top_px > content_px - viewport_px:
            canvas.yview_moveto((content_px - viewport_px) / content_px)
