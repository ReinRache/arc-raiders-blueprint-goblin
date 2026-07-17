import time
from collections.abc import Callable

import customtkinter as ctk

from arc_companion.domain.time_format import format_sync_age

# How often the "last synced" label re-renders while idle -- the bucket a
# given timestamp falls into (e.g. "<1 min" -> "1 min ago") changes just by
# time passing, with no user action to hang a refresh off of.
_SYNC_AGE_TICK_MS = 30_000

# Idle: no local changes pending. Still clickable (unlike before Stage C) --
# clicking now also refreshes friend data, which is useful on its own even
# with nothing local to push, so the label says what it'll actually do.
_SYNC_IDLE_STYLE = {
    "text": "Sync Friends",
    "fg_color": "#2B2B2B",
    "border_width": 1,
    "border_color": "#555555",
    "state": "normal",
}
# Dirty: local changes are pending — "lit up" so it's obvious there's something
# to sync, and the label reflects that this push covers more than friends now.
_SYNC_DIRTY_STYLE = {
    "text": "Sync All",
    "fg_color": "#1F6AA5",
    "border_width": 0,
    "border_color": "#1F6AA5",
    "state": "normal",
}


class ActionBar(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_sync: Callable[[], None] | None = None,
        on_scan: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(
            master, height=60, corner_radius=0, border_width=1, border_color="#2A2A2A", **kwargs
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self._on_sync = on_sync
        self._on_scan = on_scan
        self._last_synced_at: int | None = None

        self.status_label = ctk.CTkLabel(
            self, text="Storage: Local + Cloud (Supabase)", text_color="#4CAF50"
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        sync_row = ctk.CTkFrame(self, fg_color="transparent")
        sync_row.grid(row=0, column=1, padx=10, pady=15, sticky="w")

        # Text/style set immediately below via set_dirty(False). MainWindow calls
        # set_dirty(True) after a local change and set_dirty(False) once synced --
        # this is what keeps remote calls infrequent instead of firing one per click,
        # even though the button itself stays clickable in both states now.
        self.btn_sync = ctk.CTkButton(sync_row, width=120, command=self._handle_sync_click)
        self.btn_sync.grid(row=0, column=0)
        self.set_dirty(False)

        self.sync_age_label = ctk.CTkLabel(
            sync_row, text="", text_color="gray", font=ctk.CTkFont(size=11)
        )
        self.sync_age_label.grid(row=0, column=1, padx=(8, 0))
        self._refresh_sync_age_label()

        self.btn_scan = ctk.CTkButton(
            self, text="Scan Collection Screenshots", width=200, command=self._handle_scan_click
        )
        self.btn_scan.grid(row=0, column=2, padx=20, pady=15, sticky="e")

    def set_dirty(self, dirty: bool) -> None:
        self.btn_sync.configure(**(_SYNC_DIRTY_STYLE if dirty else _SYNC_IDLE_STYLE))

    def set_sync_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, text_color=color)

    def set_last_synced_at(self, epoch_seconds: int | None) -> None:
        self._last_synced_at = epoch_seconds
        self._refresh_sync_age_label()

    def _refresh_sync_age_label(self) -> None:
        age = None if self._last_synced_at is None else int(time.time()) - self._last_synced_at
        self.sync_age_label.configure(text=format_sync_age(age))
        self.after(_SYNC_AGE_TICK_MS, self._refresh_sync_age_label)

    def _handle_sync_click(self) -> None:
        if self._on_sync is not None:
            self._on_sync()

    def _handle_scan_click(self) -> None:
        if self._on_scan is not None:
            self._on_scan()
