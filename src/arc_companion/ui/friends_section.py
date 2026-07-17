from collections.abc import Callable

import customtkinter as ctk

from arc_companion.domain.friends import visible_friend_ids
from arc_companion.storage.friends_cache import FriendProfileSnapshot


class FriendsSection(ctk.CTkFrame):
    """Lives inside Sidebar, filling the space below the static nav rows.
    Shows a checkbox per friend who has actually resolved to a real cloud
    profile at least once (see domain.friends.visible_friend_ids) -- a
    roster entry that's never synced doesn't get a row here."""

    def __init__(
        self,
        master,
        friend_ids: list[str],
        active_friend_ids: list[str],
        cache: dict[str, FriendProfileSnapshot],
        on_active_changed: Callable[[list[str]], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.friend_ids = list(friend_ids)
        self.active_ids = set(active_friend_ids)
        self.cache = cache
        self.on_active_changed = on_active_changed

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="Friends", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(10, 4), sticky="w"
        )

        macro_row = ctk.CTkFrame(self, fg_color="transparent")
        macro_row.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
        ctk.CTkButton(macro_row, text="All", width=50, height=20, command=self._select_all).grid(
            row=0, column=0, padx=(0, 4)
        )
        ctk.CTkButton(macro_row, text="None", width=50, height=20, command=self._select_none).grid(
            row=0, column=1
        )

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self._checkbox_vars: dict[str, ctk.BooleanVar] = {}
        self._render()

    def update_friends(
        self,
        friend_ids: list[str],
        active_friend_ids: list[str],
        cache: dict[str, FriendProfileSnapshot],
    ) -> None:
        self.friend_ids = list(friend_ids)
        self.active_ids = set(active_friend_ids)
        self.cache = cache
        self._render()

    def _render(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self._checkbox_vars = {}

        visible_ids = visible_friend_ids(self.friend_ids, self.cache)
        if not visible_ids:
            ctk.CTkLabel(
                self.list_frame,
                text="No synced friends yet.",
                text_color="gray",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, sticky="w", padx=4, pady=4)
            return

        for i, friend_id in enumerate(visible_ids):
            var = ctk.BooleanVar(value=friend_id in self.active_ids)
            self._checkbox_vars[friend_id] = var
            checkbox = ctk.CTkCheckBox(
                self.list_frame,
                text=friend_id,
                variable=var,
                font=ctk.CTkFont(size=11),
                command=self._handle_toggle,
            )
            checkbox.grid(row=i, column=0, sticky="w", padx=4, pady=2)

    def _handle_toggle(self) -> None:
        # Preserve the active/inactive preference of any friend not currently
        # rendered (not yet synced) -- only the visible checkboxes should
        # ever change self.active_ids's membership for a given friend.
        visible_ids = set(self._checkbox_vars.keys())
        hidden_active = self.active_ids - visible_ids
        now_checked = {fid for fid, var in self._checkbox_vars.items() if var.get()}
        self.active_ids = hidden_active | now_checked
        self.on_active_changed(sorted(self.active_ids))

    def _select_all(self) -> None:
        for var in self._checkbox_vars.values():
            var.set(True)
        self._handle_toggle()

    def _select_none(self) -> None:
        for var in self._checkbox_vars.values():
            var.set(False)
        self._handle_toggle()
