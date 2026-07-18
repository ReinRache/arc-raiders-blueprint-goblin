import threading
import webbrowser
from collections.abc import Callable

import customtkinter as ctk
from supabase import Client

from arc_companion.cloud.friends import fetch_profiles_by_steam_ids
from arc_companion.domain.friends import discoverable_steam_friends
from arc_companion.identity import AddFriendError, add_friend
from arc_companion.steam import openid_auth
from arc_companion.steam.web_api import SteamFriendsListPrivateError, get_friend_list, get_player_summaries
from arc_companion.storage.local_credentials import LocalCredentials, LocalCredentialsStore


class ManageFriendsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        arbg_user_id: str,
        steam_id: str | None,
        friend_ids: list[str],
        on_friends_changed: Callable[[list[str]], None],
        on_steam_linked: Callable[[str], None],
        cloud_client: Client,
    ):
        super().__init__(master)
        self.title("Manage Friends")
        self.geometry("560x680")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.arbg_user_id = arbg_user_id
        self.steam_id = steam_id
        self.friend_ids = list(friend_ids)
        self.on_friends_changed = on_friends_changed
        self.on_steam_linked = on_steam_linked
        self.cloud_client = cloud_client
        self.credentials_store = LocalCredentialsStore()
        self._cancel_login: Callable[[], None] | None = None
        self._discover_in_flight = False
        self._discover_candidates: list[dict] = []
        self._discover_checkbox_vars: dict[str, ctk.BooleanVar] = {}
        self._discover_names: dict[str, str] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # A plain grid of sections directly on the CTkToplevel doesn't scroll,
        # and this dialog's content (Goblin ID, Friends, Steam) already
        # slightly exceeds the fixed 560x680 geometry — a growing friends list
        # would only make that worse. Scrollable body instead of taller/resizable
        # window.
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

        self._build_goblin_id_section()
        self._build_friends_section()
        self._build_steam_section()
        self._build_discover_steam_friends_section()

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
            text="Add a friend's Goblin ID to compare collections — they'll show up in the "
            "sidebar's friends list once they've synced.",
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
        frame.grid(row=2, column=0, padx=24, pady=(10, 20), sticky="ew")
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
            text="Get your own free personal key — never shared, stored only on this device.",
            text_color="gray",
            wraplength=480,
            justify="left",
        ).grid(row=7, column=0, sticky="w")
        api_key_url = "https://steamcommunity.com/dev/apikey"
        api_key_link = ctk.CTkLabel(
            frame,
            text=api_key_url.removeprefix("https://"),
            text_color="#4FA8E0",
            font=ctk.CTkFont(underline=True),
            cursor="hand2",
            anchor="w",
        )
        api_key_link.grid(row=8, column=0, sticky="w", pady=(0, 2))
        api_key_link.bind("<Button-1>", lambda _event: webbrowser.open(api_key_url))
        ctk.CTkLabel(
            frame,
            # Steam's registration form asks for a "Domain Name" even though this
            # isn't a website — confirmed via Steam's own support forums that the
            # field isn't actually verified, and "localhost" is the standard,
            # widely-used value for any non-website use of a personal key.
            text='That form asks for a "Domain Name" — since this isn\'t a website, enter '
            '"localhost".',
            text_color="gray",
            wraplength=480,
            justify="left",
        ).grid(row=9, column=0, sticky="w", pady=(0, 6))
        key_row = ctk.CTkFrame(frame, fg_color="transparent")
        key_row.grid(row=10, column=0, sticky="ew")
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
        self._refresh_discover_button_state()

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
        self._refresh_discover_button_state()

    # ---- Discover Steam friends ---------------------------------------------------

    def _build_discover_steam_friends_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=3, column=0, padx=24, pady=(10, 20), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame, text="Discover Steam Friends", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            frame,
            text="Find friends from your real Steam friends list who are also using this app. "
            "Requires Steam to be linked and a Web API key saved above.",
            text_color="gray",
            wraplength=480,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.discover_button = ctk.CTkButton(
            frame, text="Find Steam Friends", command=self._on_discover_clicked
        )
        self.discover_button.grid(row=2, column=0, sticky="w")

        self.discover_status_msg = ctk.CTkLabel(
            frame, text="", text_color="gray", wraplength=480, justify="left"
        )
        self.discover_status_msg.grid(row=3, column=0, sticky="w", pady=(6, 0))

        self.discover_results_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.discover_results_frame.grid(row=4, column=0, sticky="ew", pady=(4, 0))

        self.discover_add_button = ctk.CTkButton(
            frame, text="Add Selected", command=self._on_add_selected_clicked
        )
        # Only gridded once there are results -- see _render_discover_results.

        self._refresh_discover_button_state()

    def _refresh_discover_button_state(self) -> None:
        if not hasattr(self, "discover_button") or self._discover_in_flight:
            return
        api_key = self.credentials_store.load().steam_web_api_key
        self.discover_button.configure(state="normal" if (self.steam_id and api_key) else "disabled")

    def _on_discover_clicked(self) -> None:
        if self._discover_in_flight:
            return
        api_key = self.credentials_store.load().steam_web_api_key
        if not self.steam_id or not api_key:
            return  # button should be disabled in this case; defensive no-op

        self._discover_in_flight = True
        self.discover_button.configure(state="disabled")
        self.discover_status_msg.configure(text="Searching...", text_color="gray")
        self._clear_discover_results()

        steam_id = self.steam_id
        friend_ids_snapshot = list(self.friend_ids)

        def worker() -> None:
            try:
                steam_friend_ids = get_friend_list(api_key, steam_id)
            except SteamFriendsListPrivateError as exc:
                # str(exc) must be captured now, not inside the lambda --
                # Python auto-unbinds an `except ... as exc` name at the end
                # of the except block, and this lambda only actually runs
                # later (async, via self.after on the Tk thread), by which
                # point `exc` no longer exists in this scope (confirmed by
                # hitting the resulting NameError directly, not assumed).
                message = str(exc)
                self.after(0, lambda: self._on_discover_finished(error=message))
                return
            except Exception:
                self.after(0, lambda: self._on_discover_finished(error="Search failed — check your connection."))
                return

            try:
                matched = fetch_profiles_by_steam_ids(self.cloud_client, steam_friend_ids)
                candidates = discoverable_steam_friends(steam_friend_ids, matched, friend_ids_snapshot)
            except Exception:
                self.after(0, lambda: self._on_discover_finished(error="Search failed — check your connection."))
                return

            # Resolving display names is a nicety, not required for the
            # feature to work -- a failure here just falls back to showing
            # Goblin IDs in the checklist instead of real names.
            names: dict[str, str] = {}
            try:
                candidate_steam_ids = [c["steam_id"] for c in candidates if c.get("steam_id")]
                if candidate_steam_ids:
                    names = get_player_summaries(api_key, candidate_steam_ids)
            except Exception:
                names = {}

            self.after(0, lambda: self._on_discover_finished(candidates=candidates, names=names))

        threading.Thread(target=worker, daemon=True).start()

    def _on_discover_finished(
        self,
        candidates: list[dict] | None = None,
        names: dict[str, str] | None = None,
        error: str | None = None,
    ) -> None:
        self._discover_in_flight = False
        self._refresh_discover_button_state()

        if error is not None:
            self.discover_status_msg.configure(text=error, text_color="#E57373")
            return

        self._discover_candidates = candidates or []
        self._discover_names = names or {}
        if not self._discover_candidates:
            self.discover_status_msg.configure(
                text="No new Steam friends found on Blueprint Goblin.", text_color="gray"
            )
            return
        self.discover_status_msg.configure(text="")
        self._render_discover_results()

    def _clear_discover_results(self) -> None:
        for widget in self.discover_results_frame.winfo_children():
            widget.destroy()
        self._discover_checkbox_vars = {}
        self.discover_add_button.grid_forget()

    def _render_discover_results(self) -> None:
        self._clear_discover_results()
        for i, candidate in enumerate(self._discover_candidates):
            candidate_id = candidate["arbg_user_id"]
            display_name = self._discover_names.get(candidate.get("steam_id"), candidate_id)
            var = ctk.BooleanVar(value=False)  # opt-in: adding a friend is deliberate, not a default
            self._discover_checkbox_vars[candidate_id] = var
            ctk.CTkCheckBox(
                self.discover_results_frame,
                text=f"{display_name} ({candidate_id})",
                variable=var,
                font=ctk.CTkFont(size=12),
            ).grid(row=i, column=0, sticky="w", pady=2)
        self.discover_add_button.grid(row=5, column=0, sticky="w", pady=(6, 0))

    def _on_add_selected_clicked(self) -> None:
        selected_ids = [fid for fid, var in self._discover_checkbox_vars.items() if var.get()]
        for candidate_id in selected_ids:
            try:
                self.friend_ids = add_friend(candidate_id, self.arbg_user_id, self.friend_ids)
            except AddFriendError:
                continue  # already added or somehow self -- already filtered upstream, but harmless
        self._render_friends_list()
        self.on_friends_changed(self.friend_ids)
        self.discover_status_msg.configure(
            text=f"Added {len(selected_ids)} friend(s)." if selected_ids else "", text_color="#81C784"
        )
        self._clear_discover_results()
        self._discover_candidates = []
