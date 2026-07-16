from collections.abc import Callable

import customtkinter as ctk

from arc_companion.identity import AddFriendError, add_friend
from arc_companion.steam import openid_auth
from arc_companion.storage.local_credentials import LocalCredentials, LocalCredentialsStore


class SettingsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        arbg_user_id: str,
        steam_id: str | None,
        friend_ids: list[str],
        on_friends_changed: Callable[[list[str]], None],
        on_steam_linked: Callable[[str], None],
    ):
        super().__init__(master)
        self.title("Settings")
        self.geometry("560x680")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.arbg_user_id = arbg_user_id
        self.steam_id = steam_id
        self.friend_ids = list(friend_ids)
        self.on_friends_changed = on_friends_changed
        self.on_steam_linked = on_steam_linked
        self.credentials_store = LocalCredentialsStore()
        self._cancel_login: Callable[[], None] | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # A plain grid of sections directly on the CTkToplevel doesn't scroll,
        # and this dialog's content (Goblin ID, Friends, Steam, Wipe) already
        # slightly exceeds the fixed 560x680 geometry — a growing friends list
        # would only make that worse. Scrollable body instead of taller/resizable
        # window: content length here is expected to keep growing (more Steam
        # fields, more settings sections) as later phases land.
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

        self._build_goblin_id_section()
        self._build_friends_section()
        self._build_steam_section()
        self._build_wipe_section()

    # ---- Goblin ID -----------------------------------------------------------

    def _build_goblin_id_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(frame, text="Your Goblin ID", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            frame, text="Share this with friends so they can add you.", text_color="gray"
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        id_row = ctk.CTkFrame(frame, fg_color="transparent")
        id_row.grid(row=2, column=0, sticky="w")
        ctk.CTkLabel(id_row, text=self.arbg_user_id, font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, padx=(0, 10)
        )
        ctk.CTkButton(id_row, text="Copy", width=80, command=self._copy_own_id).grid(row=0, column=1)

    def _copy_own_id(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.arbg_user_id)

    # ---- Friends ---------------------------------------------------------------

    def _build_friends_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=1, column=0, padx=24, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Friends", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            frame,
            text="Comparing collections needs cloud sync (coming in a follow-up) — for now "
            "this just keeps your friends list.",
            text_color="gray",
            wraplength=480,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        add_row = ctk.CTkFrame(frame, fg_color="transparent")
        add_row.grid(row=2, column=0, sticky="ew")
        self.friend_entry = ctk.CTkEntry(add_row, placeholder_text="GBLN-XXXXX", width=200)
        self.friend_entry.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(add_row, text="Add", width=80, command=self._on_add_friend).grid(row=0, column=1)

        self.friend_error_label = ctk.CTkLabel(frame, text="", text_color="#E57373")
        self.friend_error_label.grid(row=3, column=0, sticky="w", pady=(4, 4))

        self.friends_list_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.friends_list_frame.grid(row=4, column=0, sticky="ew")
        self._render_friends_list()

    def _render_friends_list(self) -> None:
        for widget in self.friends_list_frame.winfo_children():
            widget.destroy()
        if not self.friend_ids:
            ctk.CTkLabel(self.friends_list_frame, text="No friends added yet.", text_color="gray").grid(
                row=0, column=0, sticky="w"
            )
            return
        for i, friend_id in enumerate(self.friend_ids):
            row = ctk.CTkFrame(self.friends_list_frame, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", pady=2)
            ctk.CTkLabel(row, text=friend_id).grid(row=0, column=0, padx=(0, 8), sticky="w")
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color="#2B2B2B",
                border_width=1,
                border_color="#555555",
                command=lambda f=friend_id: self._on_remove_friend(f),
            ).grid(row=0, column=1)

    def _on_add_friend(self) -> None:
        try:
            self.friend_ids = add_friend(self.friend_entry.get(), self.arbg_user_id, self.friend_ids)
        except AddFriendError as exc:
            self.friend_error_label.configure(text=str(exc))
            return
        self.friend_error_label.configure(text="")
        self.friend_entry.delete(0, "end")
        self._render_friends_list()
        self.on_friends_changed(self.friend_ids)

    def _on_remove_friend(self, friend_id: str) -> None:
        self.friend_ids = [f for f in self.friend_ids if f != friend_id]
        self._render_friends_list()
        self.on_friends_changed(self.friend_ids)

    # ---- Steam (optional) -------------------------------------------------------

    def _build_steam_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=2, column=0, padx=24, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame, text="Steam Account (optional)", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            frame,
            text="Link your Steam account to let the app auto-discover Steam friends later. "
            "You can fully use the app without this by sharing your Goblin ID instead.",
            text_color="gray",
            wraplength=480,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.steam_status_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(weight="bold"))
        self.steam_status_label.grid(row=2, column=0, sticky="w", pady=(0, 8))

        self.consent_var = ctk.BooleanVar(value=False)
        self.consent_check = ctk.CTkCheckBox(
            frame,
            text="I understand my SteamID will be stored to enable friend features",
            variable=self.consent_var,
            command=self._update_steam_button_state,
        )
        self.consent_check.grid(row=3, column=0, sticky="w", pady=(0, 8))

        self.steam_button = ctk.CTkButton(frame, text="Link Steam Account", command=self._on_steam_button)
        self.steam_button.grid(row=4, column=0, sticky="w")

        self.steam_status_msg = ctk.CTkLabel(
            frame, text="", text_color="gray", wraplength=480, justify="left"
        )
        self.steam_status_msg.grid(row=5, column=0, sticky="w", pady=(6, 0))

        ctk.CTkLabel(frame, text="Steam Web API Key", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=6, column=0, sticky="w", pady=(14, 2)
        )
        ctk.CTkLabel(
            frame,
            text="Get your own free personal key at steamcommunity.com/dev/apikey — never shared, "
            "stored only on this device.",
            text_color="gray",
            wraplength=480,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(0, 6))
        key_row = ctk.CTkFrame(frame, fg_color="transparent")
        key_row.grid(row=8, column=0, sticky="ew")
        self.api_key_entry = ctk.CTkEntry(key_row, width=300, show="*")
        self.api_key_entry.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(key_row, text="Save", width=80, command=self._on_save_api_key).grid(row=0, column=1)

        existing = self.credentials_store.load()
        if existing.steam_web_api_key:
            self.api_key_entry.insert(0, existing.steam_web_api_key)

        self._refresh_steam_status()

    def _refresh_steam_status(self) -> None:
        if self.steam_id:
            self.steam_status_label.configure(text=f"Linked as {self.steam_id}", text_color="#81C784")
            self.steam_button.configure(text="Switch Account")
        else:
            self.steam_status_label.configure(text="Not linked", text_color="gray")
            self.steam_button.configure(text="Link Steam Account")
        self._update_steam_button_state()

    def _update_steam_button_state(self) -> None:
        if self._cancel_login is not None:
            return  # a login is in flight; button is repurposed as Cancel
        if self.steam_id:
            self.steam_button.configure(state="normal")
        else:
            self.steam_button.configure(state="normal" if self.consent_var.get() else "disabled")

    def _on_steam_button(self) -> None:
        if self._cancel_login is not None:
            self._cancel_login()
            self._cancel_login = None
            self._refresh_steam_status()
            self.steam_status_msg.configure(text="Login cancelled.")
            return

        self.steam_button.configure(text="Cancel Login", state="normal")
        self.steam_status_msg.configure(text="Complete the login in your browser, then return here.")

        def handle_result(steam_id: str | None) -> None:
            self.after(0, lambda: self._on_login_complete(steam_id))

        self._cancel_login = openid_auth.login(handle_result)

    def _on_login_complete(self, steam_id: str | None) -> None:
        self._cancel_login = None
        if steam_id is None:
            self.steam_status_msg.configure(text="Steam login didn't complete (cancelled, timed out, or failed).")
            self._refresh_steam_status()
            return
        self.steam_id = steam_id
        self.steam_status_msg.configure(text="")
        self._refresh_steam_status()
        self.on_steam_linked(steam_id)

    def _on_save_api_key(self) -> None:
        key = self.api_key_entry.get().strip()
        self.credentials_store.save(LocalCredentials(steam_web_api_key=key or None))

    # ---- Wipe cloud data (placeholder) -------------------------------------------

    def _build_wipe_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=3, column=0, padx=24, pady=(10, 20), sticky="ew")
        ctk.CTkButton(
            frame,
            text="Wipe Cloud Data",
            fg_color="#2B2B2B",
            border_width=1,
            border_color="#555555",
            state="disabled",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(frame, text="Available once cloud sync is set up.", text_color="gray").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
