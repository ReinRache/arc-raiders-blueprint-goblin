import threading
from collections.abc import Callable
from tkinter import messagebox

import customtkinter as ctk
from supabase import Client

from arc_companion.cloud.errors import describe_error
from arc_companion.cloud.friends import fetch_profiles_by_steam_ids
from arc_companion.cloud.steam_proxy import (
    SteamFriendsListPrivateError,
    SteamProxyRateLimitedError,
    consolidate_steam_profiles,
    get_friend_list,
    get_player_summaries,
)
from arc_companion.cloud.sync import ensure_session
from arc_companion.domain.friends import discoverable_steam_friends
from arc_companion.identity import AddFriendError, add_friend
from arc_companion.steam import openid_auth
from arc_companion.storage.supabase_session import SupabaseSessionStore
from arc_companion.ui.theme import ERROR_COLOR, NEUTRAL_BUTTON_BORDER_COLOR, NEUTRAL_BUTTON_COLOR, SUCCESS_COLOR_LIGHT


class SteamFriendsDialog(ctk.CTkToplevel):
    """Everything Steam-related, split out of the old combined Manage Friends
    dialog: link/switch the Steam account, find Steam friends who also use
    the app, and clean up obsolete duplicate collections. Goblin-ID-based
    friends live in GoblinFriendsDialog."""

    def __init__(
        self,
        master,
        arbg_user_id: str,
        steam_id: str | None,
        friend_ids: list[str],
        on_friends_changed: Callable[[list[str]], None],
        on_steam_linked: Callable[[str], None],
        cloud_client: Client,
        cloud_session_store: SupabaseSessionStore,
    ):
        super().__init__(master)
        self.title("Steam ID Friends")
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
        self.cloud_session_store = cloud_session_store

        self._cancel_login: Callable[[], None] | None = None
        # Consolidation can't reuse the routine login above -- Steam's
        # check_authentication only accepts an assertion once, and the
        # routine flow already spends it locally. Clicking "Clean Up
        # Obsolete Collections" triggers its own separate, never-locally-
        # verified login instead (see openid_auth.login's verify_locally),
        # so the server gets the only check_authentication call for it.
        self._cancel_consolidate_login: Callable[[], None] | None = None
        self._consolidate_in_flight = False
        self._discover_in_flight = False
        self._discover_candidates: list[dict] = []
        self._discover_checkbox_vars: dict[str, ctk.BooleanVar] = {}
        self._discover_names: dict[str, str] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)


        self.grid_columnconfigure(0, weight=1)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

        self._build_steam_section()
        self._build_discover_steam_friends_section()


    def _build_steam_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        # pady=10 (not (10, 20)) matches the friends section's rhythm --
        # the extra bottom margin was sized for this frame back when it
        # also held the now-deleted Steam Web API Key block.
        frame.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="ew")
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

        # height=18 overrides CTkLabel's default (28px, unrelated to actual
        # text) -- this label is empty except during/right after a login
        # attempt, and the unused default height was reserving real blank
        # space above the next section even when there was nothing to show.
        self.steam_status_msg = ctk.CTkLabel(
            frame, text="", text_color="gray", wraplength=480, justify="left", height=18
        )
        self.steam_status_msg.grid(row=5, column=0, sticky="w", pady=(6, 0))

        # Enabled once Steam is linked at all. Repeated test installs linking
        # the same real Steam account each mint their own Goblin ID, leaving
        # duplicate cloud rows; this cleans those up. Clicking it runs its
        # own dedicated Steam login (never reuses the routine one above --
        # see _cancel_consolidate_login) so the server independently
        # re-verifies ownership itself (cloud/steam_proxy.py:
        # consolidate_steam_profiles) rather than trusting a claimed
        # steam_id, since SteamID64s are usually publicly discoverable.
        self.consolidate_button = ctk.CTkButton(
            frame,
            text="Clean Up Obsolete Collections",
            fg_color=NEUTRAL_BUTTON_COLOR,
            border_width=1,
            border_color=NEUTRAL_BUTTON_BORDER_COLOR,
            state="disabled",
            command=self._on_consolidate_clicked,
        )
        self.consolidate_button.grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.consolidate_status_msg = ctk.CTkLabel(
            frame, text="", text_color="gray", wraplength=480, justify="left", height=18
        )
        self.consolidate_status_msg.grid(row=7, column=0, sticky="w", pady=(6, 0))

        self._refresh_steam_status()

    def _refresh_steam_status(self) -> None:
        if self.steam_id:
            self.steam_status_label.configure(text=f"Linked as {self.steam_id}", text_color=SUCCESS_COLOR_LIGHT)
            self.steam_button.configure(text="Switch Steam Account")
        else:
            self.steam_status_label.configure(text="Not linked", text_color="gray")
            self.steam_button.configure(text="Link Steam Account")
        self._update_steam_button_state()
        self._refresh_discover_button_state()
        self._refresh_consolidate_button_state()

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

        def handle_result(steam_id: str | None, raw_params: dict[str, str] | None) -> None:
            # raw_params is unused here -- routine linking only needs the
            # already locally-verified steam_id. See
            # _cancel_consolidate_login for why these params can't also be
            # reused for server-side verification.
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

    # ---- Clean up duplicate Steam profiles ---------------------------------------

    def _refresh_consolidate_button_state(self) -> None:
        if (
            not hasattr(self, "consolidate_button")
            or self._consolidate_in_flight
            or self._cancel_consolidate_login is not None
        ):
            return
        self.consolidate_button.configure(state="normal" if self.steam_id else "disabled")

    def _on_consolidate_clicked(self) -> None:
        if self._cancel_consolidate_login is not None:
            self._cancel_consolidate_login()
            self._cancel_consolidate_login = None
            self.consolidate_button.configure(text="Clean Up Obsolete Collections")
            self._refresh_consolidate_button_state()
            self.consolidate_status_msg.configure(text="Login cancelled.", text_color="gray")
            return
        if self._consolidate_in_flight or not self.steam_id:
            return
        if not messagebox.askyesno(
            "Clean Up Obsolete Collections",
            "This confirms your Steam login again (a separate login from linking, since "
            "Steam only lets each login be verified once), then marks every other cloud "
            "profile linked to that same Steam account as obsolete, keeping only this one. "
            "It only affects duplicate cloud entries, not your local collection. Continue?",
            parent=self,
        ):
            return

        self.consolidate_button.configure(text="Cancel Login", state="normal")
        self.consolidate_status_msg.configure(
            text="Complete the login in your browser, then return here.", text_color="gray"
        )

        def handle_result(_steam_id: str | None, raw_params: dict[str, str] | None) -> None:
            self.after(0, lambda: self._on_consolidate_login_complete(raw_params))

        self._cancel_consolidate_login = openid_auth.login(handle_result, verify_locally=False)

    def _on_consolidate_login_complete(self, raw_params: dict[str, str] | None) -> None:
        self._cancel_consolidate_login = None
        self.consolidate_button.configure(text="Clean Up Obsolete Collections")
        if raw_params is None:
            self._refresh_consolidate_button_state()
            self.consolidate_status_msg.configure(
                text="Steam login didn't complete (cancelled, timed out, or failed).", text_color="gray"
            )
            return

        self._consolidate_in_flight = True
        self.consolidate_button.configure(state="disabled")
        self.consolidate_status_msg.configure(text="Cleaning up...", text_color="gray")

        def worker() -> None:
            try:
                ensure_session(self.cloud_client, self.cloud_session_store)
                count = consolidate_steam_profiles(self.cloud_client, raw_params)
            except Exception as exc:
                error_code = describe_error(exc)
                message = f"Clean up failed ({error_code}) — check your connection."
                self.after(0, lambda: self._on_consolidate_finished(error=message))
                return
            self.after(0, lambda: self._on_consolidate_finished(count=count))

        threading.Thread(target=worker, daemon=True).start()

    def _on_consolidate_finished(self, count: int | None = None, error: str | None = None) -> None:
        self._consolidate_in_flight = False
        self._refresh_consolidate_button_state()

        if error is not None:
            self.consolidate_status_msg.configure(text=error, text_color=ERROR_COLOR)
            return
        if count:
            self.consolidate_status_msg.configure(
                text=f"Cleaned up {count} obsolete collection(s).", text_color=SUCCESS_COLOR_LIGHT
            )
        else:
            self.consolidate_status_msg.configure(text="No obsolete collections found.", text_color="gray")

    # ---- Discover Steam friends ---------------------------------------------------

    def _build_discover_steam_friends_section(self) -> None:
        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.grid(row=1, column=0, padx=24, pady=(10, 20), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame, text="Discover Steam Friends", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            frame,
            text="Find friends from your real Steam friends list who are also using this app. "
            "Requires Steam to be linked above.",
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

        # Scrollable because the result count is unbounded (a big Steam
        # friends list); gridded only once there are results (see
        # _render_discover_results) so an empty search doesn't reserve space.
        self.discover_results_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent", height=150)

        self.discover_add_button = ctk.CTkButton(
            frame, text="Add Selected", command=self._on_add_selected_clicked
        )
        # Only gridded once there are results -- see _render_discover_results.

        self._refresh_discover_button_state()

    def _refresh_discover_button_state(self) -> None:
        if not hasattr(self, "discover_button") or self._discover_in_flight:
            return
        self.discover_button.configure(state="normal" if self.steam_id else "disabled")

    def _on_discover_clicked(self) -> None:
        if self._discover_in_flight:
            return
        if not self.steam_id:
            return  # button should be disabled in this case; defensive no-op

        self._discover_in_flight = True
        self.discover_button.configure(state="disabled")
        self.discover_status_msg.configure(text="Searching...", text_color="gray")
        self._clear_discover_results()

        steam_id = self.steam_id
        friend_ids_snapshot = list(self.friend_ids)

        def worker() -> None:
            try:
                # The Steam proxy Edge Functions require an authenticated
                # Supabase session (verify_jwt) -- unlike the plain profile
                # reads below, which are publicly readable under RLS.
                ensure_session(self.cloud_client, self.cloud_session_store)
                steam_friend_ids = get_friend_list(self.cloud_client, steam_id)
            except (SteamFriendsListPrivateError, SteamProxyRateLimitedError) as exc:
                # str(exc) must be captured now, not inside the lambda --
                # Python auto-unbinds an `except ... as exc` name at the end
                # of the except block, and this lambda only actually runs
                # later (async, via self.after on the Tk thread), by which
                # point `exc` no longer exists in this scope (confirmed by
                # hitting the resulting NameError directly, not assumed).
                message = str(exc)
                self.after(0, lambda: self._on_discover_finished(error=message))
                return
            except Exception as exc:
                # Exception class name, not the full message -- always
                # available regardless of which library raised it, short
                # enough to show inline, specific enough to be worth
                # reporting back instead of a dead-end generic message.
                # Captured now, not inside the lambda -- see the comment
                # on the SteamFriendsListPrivateError branch above.
                error_code = describe_error(exc)
                self.after(
                    0, lambda: self._on_discover_finished(error=f"Search failed ({error_code}) — check your connection.")
                )
                return

            try:
                matched = fetch_profiles_by_steam_ids(self.cloud_client, steam_friend_ids)
                candidates = discoverable_steam_friends(steam_friend_ids, matched, friend_ids_snapshot)
            except Exception as exc:
                error_code = describe_error(exc)
                self.after(
                    0, lambda: self._on_discover_finished(error=f"Search failed ({error_code}) — check your connection.")
                )
                return

            # Resolving display names is a nicety, not required for the
            # feature to work -- a failure here just falls back to showing
            # Goblin IDs in the checklist instead of real names.
            names: dict[str, str] = {}
            try:
                candidate_steam_ids = [c["steam_id"] for c in candidates if c.get("steam_id")]
                if candidate_steam_ids:
                    names = get_player_summaries(self.cloud_client, candidate_steam_ids)
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
            self.discover_status_msg.configure(text=error, text_color=ERROR_COLOR)
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
        self.discover_results_frame.grid_forget()

    def _render_discover_results(self) -> None:
        self._clear_discover_results()
        for i, candidate in enumerate(self._discover_candidates):
            candidate_id = candidate["arbg_user_id"]
            display_name = self._discover_names.get(candidate.get("steam_id"), candidate_id)
            # Checked by default: someone who ran "Find Steam Friends" almost
            # always wants to add the people it found, so the common path is
            # one click ("Add Selected"); uncheck anyone to skip them.
            var = ctk.BooleanVar(value=True)
            self._discover_checkbox_vars[candidate_id] = var
            ctk.CTkCheckBox(
                self.discover_results_frame,
                text=f"{display_name} ({candidate_id})",
                variable=var,
                font=ctk.CTkFont(size=12),
            ).grid(row=i, column=0, sticky="w", pady=2)
        self.discover_results_frame.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        self.discover_add_button.grid(row=5, column=0, sticky="w", pady=(6, 0))

    def _on_add_selected_clicked(self) -> None:
        selected_ids = [fid for fid, var in self._discover_checkbox_vars.items() if var.get()]
        for candidate_id in selected_ids:
            try:
                self.friend_ids = add_friend(candidate_id, self.arbg_user_id, self.friend_ids)
            except AddFriendError:
                continue  # already added or somehow self -- already filtered upstream, but harmless
        self.on_friends_changed(self.friend_ids)
        self.discover_status_msg.configure(
            text=f"Added {len(selected_ids)} friend(s)." if selected_ids else "", text_color=SUCCESS_COLOR_LIGHT
        )
        self._clear_discover_results()
        self._discover_candidates = []
