import tkinter
from collections.abc import Callable

import customtkinter as ctk
from PIL import Image

from arc_companion.data.blueprints import Blueprint
from arc_companion.domain.friends import FriendStatusCounts, Highlight, compute_highlight
from arc_companion.domain.status import BlueprintStatus
from arc_companion.ui.theme import HIGHLIGHT_COLORS, STATUS_COLORS
from arc_companion.ui.tooltip import Tooltip

_ICON_SIZE = (60, 60)
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


def _load_icon(blueprint: Blueprint) -> ctk.CTkImage | None:
    if not blueprint.image_path.exists():
        return None
    image = Image.open(blueprint.image_path).convert("RGBA")
    return ctk.CTkImage(light_image=image, dark_image=image, size=_ICON_SIZE)


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

        if icon is not None:
            self._icon = icon  # keep a reference alive; Tk drops images with no referrer
            icon_label = ctk.CTkLabel(self, image=icon, text="")
            icon_label.grid(row=0, column=0, padx=15, pady=(8, 2))
        else:
            placeholder = ctk.CTkFrame(
                self, width=_ICON_SIZE[0], height=_ICON_SIZE[1], fg_color="#1F538D", corner_radius=4
            )
            placeholder.grid_propagate(False)
            placeholder.grid(row=0, column=0, padx=15, pady=(8, 2))

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
        self.status_btn.grid(row=2, column=0, padx=10, pady=(2, 4))

        # Friends overlay row: a small icon + one dot per BlueprintStatus,
        # each showing how many active friends are in that state and, on
        # hover, listing their names.
        friends_row = ctk.CTkFrame(self, fg_color="transparent")
        friends_row.grid(row=3, column=0, padx=6, pady=(0, 6))
        ctk.CTkLabel(friends_row, text="\U0001F465", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, padx=(0, 4)
        )
        self._dot_labels: dict[BlueprintStatus, ctk.CTkLabel] = {}
        for i, dot_status in enumerate(BlueprintStatus, start=1):
            _, fg, _ = STATUS_COLORS[dot_status]
            dot = ctk.CTkLabel(friends_row, text="●0", font=ctk.CTkFont(size=11), text_color=fg)
            dot.grid(row=0, column=i, padx=2)
            Tooltip(dot, (lambda s=dot_status: self._tooltip_text_for(s)))
            self._dot_labels[dot_status] = dot

        self.set_status(status)
        self.set_friend_overlay(friend_counts, highlight)

    def _tooltip_text_for(self, status: BlueprintStatus) -> str:
        return "\n".join(self._friend_counts.for_status(status))

    def set_status(self, status: BlueprintStatus) -> None:
        self._status = status
        text, color, hover = STATUS_COLORS[status]
        self.status_btn.configure(text=text, fg_color=color, hover_color=hover)

    def set_friend_overlay(self, friend_counts: FriendStatusCounts, highlight: Highlight) -> None:
        self._friend_counts = friend_counts
        for dot_status, label in self._dot_labels.items():
            count = len(friend_counts.for_status(dot_status))
            label.configure(text=f"●{count}")
        border_width, border_color = HIGHLIGHT_COLORS[highlight]
        self.configure(border_width=border_width, border_color=border_color)


# Public (no leading underscore): main_window.py uses this to size the
# window itself so the default/minimum widths land on an exact number of
# columns with no leftover slack — see MainWindow's _GRID_OVERHEAD_PX.
CELL_SIZE = _CARD_WIDTH + _CARD_GAP


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
        self._icon_cache: dict[int, ctk.CTkImage | None] = {}
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
        self.render()

    def refresh_status(self, blueprint_id: int) -> None:
        # My own status is itself an input to compute_highlight(), so a
        # status change needs the overlay recomputed too, not just re-styled.
        if blueprint_id in self.cards:
            self.cards[blueprint_id].set_status(self.status_for_id(blueprint_id))
            self._refresh_card_overlay(blueprint_id)

    def refresh_friend_overlay(self) -> None:
        for blueprint_id in self.cards:
            self._refresh_card_overlay(blueprint_id)

    def _refresh_card_overlay(self, blueprint_id: int) -> None:
        counts = self.friend_counts_for_id(blueprint_id)
        highlight = compute_highlight(self.status_for_id(blueprint_id), counts)
        self.cards[blueprint_id].set_friend_overlay(counts, highlight)

    def _get_icon(self, blueprint: Blueprint) -> ctk.CTkImage | None:
        if blueprint.id not in self._icon_cache:
            self._icon_cache[blueprint.id] = _load_icon(blueprint)
        return self._icon_cache[blueprint.id]

    def render(self) -> None:
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
                    self._get_icon(bp),
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
        tkinter.Frame.configure(self, height=content_height)
