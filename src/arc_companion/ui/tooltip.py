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
        self._popup.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 8}")
        label = tkinter.Label(
            self._popup,
            text=text,
            background=TOOLTIP_BG_COLOR,
            foreground=TOOLTIP_FG_COLOR,
            borderwidth=1,
            relief="solid",
            padx=6,
            pady=3,
            justify="left",
        )
        label.pack()

    def _on_leave(self, event) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
