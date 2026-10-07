from collections.abc import Callable

import customtkinter as ctk

from arc_companion.identity import AddFriendError, add_friend
from arc_companion.storage.friends_cache import FriendProfileSnapshot
from arc_companion.ui.theme import ERROR_COLOR, NEUTRAL_BUTTON_BORDER_COLOR, NEUTRAL_BUTTON_COLOR


class GoblinFriendsDialog(ctk.CTkToplevel):
    """Your Goblin ID plus the friends you've added by theirs. Steam-based
    features (linking, finding Steam friends) are in SteamFriendsDialog."""

    def __init__(
        self,
        master,
        arbg_user_id: str,
        friend_ids: list[str],
        friends_cache: dict[str, FriendProfileSnapshot],
        on_friends_changed: Callable[[list[str]], None],
    ):
        super().__init__(master)
        self.title("Goblin ID Friends")
        self.geometry("520x540")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.arbg_user_id = arbg_user_id
        self.friend_ids = list(friend_ids)
        # A snapshot at dialog-open time, same as friend_ids above -- won't
        # pick up a Steam name resolved by a sync that happens while this
        # dialog is still open. Used purely for display (which friend you're
        # about to remove); nothing here is keyed on it.
        self.friends_cache = friends_cache
        self.on_friends_changed = on_friends_changed

        self.grid_columnconfigure(0, weight=1)
        # The friends section is the one growable row; only its list scrolls
        # (the one unbounded part) -- the ID and add-a-friend rows stay put.
        self.grid_rowconfigure(1, weight=1)

        self._build_goblin_id_section()
        self._build_friends_section()

    # ---- Goblin ID -----------------------------------------------------------

    def _build_goblin_id_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
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
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=24, pady=(10, 20), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(4, weight=1)

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

        self.friend_error_label = ctk.CTkLabel(frame, text="", text_color=ERROR_COLOR)
        self.friend_error_label.grid(row=3, column=0, sticky="w", pady=(4, 4))

        self.friends_list_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.friends_list_frame.grid(row=4, column=0, sticky="nsew")
        self.friends_list_frame.grid_columnconfigure(0, weight=1)
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
            ctk.CTkLabel(row, text=self._friend_label(friend_id)).grid(row=0, column=0, padx=(0, 8), sticky="w")
            ctk.CTkButton(
                row,
                text="Remove",
                width=70,
                fg_color=NEUTRAL_BUTTON_COLOR,
                border_width=1,
                border_color=NEUTRAL_BUTTON_BORDER_COLOR,
                command=lambda f=friend_id: self._on_remove_friend(f),
            ).grid(row=0, column=1)

    def _friend_label(self, friend_id: str) -> str:
        # Goblin ID stays the primary label (it's what Remove actually acts
        # on, and what you'd type to re-add someone) with the Steam name
        # appended when known, rather than swapping to it entirely the way
        # the sidebar's compact friend list does -- there's room here, and
        # showing both is what actually answers "who am I about to remove."
        snapshot = self.friends_cache.get(friend_id)
        if snapshot is not None and snapshot.steam_name:
            return f"{friend_id} ({snapshot.steam_name})"
        return friend_id

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

