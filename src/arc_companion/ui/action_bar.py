from collections.abc import Callable

import customtkinter as ctk

# Idle: no local changes since the last sync (nothing to push once Phase 3 adds a cloud store).
_SYNC_IDLE_STYLE = {
    "fg_color": "#2B2B2B",
    "border_width": 1,
    "border_color": "#555555",
    "state": "disabled",
}
# Dirty: local changes are pending — "lit up" so it's obvious there's something to sync.
_SYNC_DIRTY_STYLE = {
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

        # Honest for Phase 1: there is no cloud yet, so this doesn't claim one exists
        self.status_label = ctk.CTkLabel(
            self, text="Storage: Local (config.json)", text_color="#4CAF50"
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # Starts idle/disabled; MainWindow calls set_dirty(True) after a local change,
        # and set_dirty(False) once that change has been synced (or acknowledged, until
        # Phase 3 adds a real cloud push). This is what keeps remote calls infrequent
        # instead of firing one per click.
        self.btn_sync = ctk.CTkButton(
            self, text="Sync Changes", width=120, command=self._handle_sync_click
        )
        self.btn_sync.grid(row=0, column=1, padx=10, pady=15, sticky="w")
        self.set_dirty(False)

        self.btn_scan = ctk.CTkButton(
            self, text="Scan Collection Screenshots", width=200, command=self._handle_scan_click
        )
        self.btn_scan.grid(row=0, column=2, padx=20, pady=15, sticky="e")

    def set_dirty(self, dirty: bool) -> None:
        self.btn_sync.configure(**(_SYNC_DIRTY_STYLE if dirty else _SYNC_IDLE_STYLE))

    def _handle_sync_click(self) -> None:
        if self._on_sync is not None:
            self._on_sync()

    def _handle_scan_click(self) -> None:
        if self._on_scan is not None:
            self._on_scan()
