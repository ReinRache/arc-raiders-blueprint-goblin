import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk
from supabase import Client

from arc_companion.cloud.errors import describe_error
from arc_companion.cloud.sync import ensure_session, wipe_cloud_data
from arc_companion.storage.supabase_session import SupabaseSessionStore
from arc_companion.version import UpdateInfo, __version__
from arc_companion.ui.theme import ERROR_COLOR, NEUTRAL_BUTTON_BORDER_COLOR, NEUTRAL_BUTTON_COLOR, SUCCESS_COLOR_LIGHT

# Not a secret, not user-specific -- the designer's own donation link.
SUPPORT_URL = "https://buymeacoffee.com/alwaysbegoblin"


class OptionsDialog(ctk.CTkToplevel):
    """General app options, separate from the friends dialogs (GoblinFriendsDialog,
    SteamFriendsDialog). Starts minimal -- delete-my-data and a
    support link -- more sections land here over time."""

    def __init__(
        self,
        master,
        cloud_client: Client,
        cloud_session_store: SupabaseSessionStore,
        available_update: UpdateInfo | None = None,
    ):
        super().__init__(master)
        self.title("Options")
        self.geometry("420x330")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.cloud_client = cloud_client
        self.cloud_session_store = cloud_session_store
        self._wipe_in_flight = False
        self.available_update = available_update

        self.grid_columnconfigure(0, weight=1)

        self._build_support_section()
        self._build_delete_data_section()
        self._build_version_section()

    # ---- Support this project ----------------------------------------------------

    def _build_support_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="ew")

        ctk.CTkButton(
            frame, text="☕ Support This Project", command=self._on_support_clicked
        ).grid(row=0, column=0, sticky="w")

    def _on_support_clicked(self) -> None:
        webbrowser.open(SUPPORT_URL)

    # ---- Delete my data -------------------------------------------------------

    def _build_delete_data_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=24, pady=(10, 20), sticky="ew")
        self.delete_data_button = ctk.CTkButton(
            frame,
            text="Delete My Data",
            fg_color=NEUTRAL_BUTTON_COLOR,
            border_width=1,
            border_color=NEUTRAL_BUTTON_BORDER_COLOR,
            command=self._on_delete_data_clicked,
        )
        self.delete_data_button.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            frame,
            text="Clears your synced blueprint data from the cloud. Your Goblin ID and local "
            "collection on this device aren't affected.",
            text_color="gray",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.delete_data_status_msg = ctk.CTkLabel(
            frame, text="", text_color="gray", wraplength=360, justify="left"
        )
        self.delete_data_status_msg.grid(row=2, column=0, sticky="w", pady=(6, 0))

    def _on_delete_data_clicked(self) -> None:
        if self._wipe_in_flight:
            return
        if not messagebox.askyesno(
            "Delete My Data",
            "This clears your synced blueprint data from the cloud (arbg_user_id and any "
            "linked SteamID stay associated with your profile row). Your local collection on "
            "this device is not affected. Continue?",
            parent=self,
        ):
            return

        self._wipe_in_flight = True
        self.delete_data_button.configure(state="disabled")
        self.delete_data_status_msg.configure(text="Deleting...", text_color="gray")

        def worker() -> None:
            try:
                user_id = ensure_session(self.cloud_client, self.cloud_session_store)
                wipe_cloud_data(self.cloud_client, user_id)
            except Exception as exc:
                # Exception class name, not the full message -- always
                # available regardless of which library raised it, short
                # enough to show inline, specific enough to be worth
                # reporting back instead of a dead-end generic message.
                # Captured now, not inside the lambda -- see the
                # SteamFriendsListPrivateError precedent in
                # steam_friends_dialog.py for why.
                error_code = describe_error(exc)
                self.after(0, lambda: self._on_delete_data_finished(success=False, error_code=error_code))
            else:
                self.after(0, lambda: self._on_delete_data_finished(success=True))

        threading.Thread(target=worker, daemon=True).start()

    def _on_delete_data_finished(self, success: bool, error_code: str | None = None) -> None:
        self._wipe_in_flight = False
        self.delete_data_button.configure(state="normal")
        if success:
            self.delete_data_status_msg.configure(text="Cloud data deleted.", text_color=SUCCESS_COLOR_LIGHT)
        else:
            self.delete_data_status_msg.configure(
                text=f"Delete failed ({error_code}) — check your connection.", text_color=ERROR_COLOR
            )

    # ---- Version -----------------------------------------------------------------

    def _build_version_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, padx=24, pady=(0, 20), sticky="ew")
        ctk.CTkLabel(frame, text=f"Version {__version__}", text_color="gray").grid(row=0, column=0, sticky="w")
        if self.available_update is not None:
            update = self.available_update
            ctk.CTkButton(
                frame,
                text=f"Update available: v{update.version}",
                command=lambda: webbrowser.open(update.url),
            ).grid(row=1, column=0, sticky="w", pady=(6, 0))
