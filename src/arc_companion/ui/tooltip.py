import tkinter

import customtkinter as ctk

from arc_companion.ui.theme import TOOLTIP_BG_COLOR, TOOLTIP_FG_COLOR


class Tooltip:
    """Hover tooltip for a widget -- CTk has no built-in equivalent. Binds
    <Enter>/<Leave> to show/hide a small borderless popup near the cursor.
    Text is supplied lazily via a callable so callers can update the content
    (e.g. friend names) without rebuilding the binding."""

    def __init__(self, widget: ctk.CTkBaseClass, text_provider):
        self._widget = widget
        self._text_provider = text_provider
        self._popup: tkinter.Toplevel | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event) -> None:
        text = self._text_provider()
        if not text:
            return
        self._popup = tkinter.Toplevel(self._widget)
        self._popup.wm_overrideredirect(True)
        # Plain tkinter, not a CTk widget -- none of CTk's own scaling
        # machinery (_apply_widget_scaling/_apply_argument_scaling/font
        # scaling) ever touches it automatically the way it does every
        # other widget in this app. Reported as looking broken/tiny on a
        # tester's high-DPI multi-monitor setup -- explicitly scaled here
        # via the same widget's own _apply_widget_scaling/_apply_font_
        # scaling (self._widget is always a real CTk widget) rather than
        # relying on Windows' bitmap-stretching compatibility layer to
        # happen to cover a plain tkinter.Toplevel consistently with
        # everything else.
        family, size = self._widget._apply_font_scaling(("", 11))
        label = tkinter.Label(
            self._popup,
            text=text,
            background=TOOLTIP_BG_COLOR,
            foreground=TOOLTIP_FG_COLOR,
            borderwidth=1,
            relief="solid",
            padx=self._widget._apply_widget_scaling(2),
            pady=self._widget._apply_widget_scaling(2),
            justify="left",
            font=(family, size),
        )
        label.pack()

        # Anchored up-and-left of the cursor, not down-right -- a normal
        # arrow cursor's own glyph extends down-right from its hotspot, the
        # same direction a down-right offset places the tooltip in, so a
        # large cursor (e.g. an accessibility/oversized cursor, reported by
        # a tester) can visually overlap and obscure it. "Up-left" means
        # anchoring the popup's bottom-right corner near the cursor rather
        # than its top-left, which needs its real rendered size first.
        self._popup.update_idletasks()
        width = self._popup.winfo_reqwidth()
        height = self._popup.winfo_reqheight()
        gap_x = self._widget._apply_widget_scaling(5)
        gap_y = self._widget._apply_widget_scaling(5)
        self._popup.wm_geometry(f"+{event.x_root - gap_x - width}+{event.y_root - gap_y - height}")

    def _on_leave(self, event) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
