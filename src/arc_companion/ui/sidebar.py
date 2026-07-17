from collections.abc import Callable

import customtkinter as ctk

from arc_companion.storage.friends_cache import FriendProfileSnapshot
from arc_companion.ui.friends_section import FriendsSection

# Public (no leading underscore): main_window.py uses this for its column's
# minsize instead of a duplicated literal, so the two can never drift apart.
SIDEBAR_WIDTH = 220


class Sidebar(ctk.CTkFrame):
    def __init__(
        self,
        master,
        total_blueprints: int,
        friend_ids: list[str],
        active_friend_ids: list[str],
        friends_cache: dict[str, FriendProfileSnapshot],
        on_manage_friends: Callable[[], None] | None = None,
        on_settings: Callable[[], None] | None = None,
        on_active_friends_changed: Callable[[list[str]], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, width=SIDEBAR_WIDTH, corner_radius=0, **kwargs)
        # FriendsSection's CTkScrollableFrame has its own natural width
        # (measured at 223px, wider than SIDEBAR_WIDTH, presumably its
        # default scrollbar allowance) -- without this, that pushed the
        # whole sidebar 11px wider than intended, silently stealing a full
        # column from the blueprint grid at the app's default window size
        # (10 -> 9). grid_propagate(False) locks this frame's own width to
        # exactly SIDEBAR_WIDTH regardless of what any child requests, same
        # technique BlueprintCard already uses against its own children.
        self.grid_propagate(False)
        self.total_blueprints = total_blueprints
        # Row 3 (FriendsSection) is the one growable row -- static nav stays
        # a fixed height at the top, the friends list fills and internally
        # scrolls through whatever's left below it. No new column, no width
        # change: friend comparison is ambient here, not a separate screen.
        self.grid_rowconfigure(3, weight=1)

        self.logo_label = ctk.CTkLabel(
            self,
            text="Arc Raiders\nBlueprint Goblin",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30), sticky="w")

        # "My Blueprints" and its owned-count label are gone -- the app has
        # exactly one view (the friend-aware grid) and the count moved into
        # the main headline (see MainWindow._header_text) instead of being
        # duplicated here.
        self.btn_manage_friends = ctk.CTkButton(
            self,
            text="Manage Friends",
            fg_color="transparent",
            anchor="w",
            command=self._handle_manage_friends_click,
        )
        self.btn_manage_friends.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        self._on_manage_friends = on_manage_friends

        self.btn_settings = ctk.CTkButton(
            self,
            text="Settings",
            fg_color="transparent",
            anchor="w",
            command=self._handle_settings_click,
        )
        self.btn_settings.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self._on_settings = on_settings

        self._on_active_friends_changed = on_active_friends_changed
        self.friends_section = FriendsSection(
            self,
            friend_ids=friend_ids,
            active_friend_ids=active_friend_ids,
            cache=friends_cache,
            on_active_changed=self._handle_active_friends_changed,
        )
        self.friends_section.grid(row=3, column=0, sticky="nsew")

    def _handle_manage_friends_click(self) -> None:
        if self._on_manage_friends is not None:
            self._on_manage_friends()

    def _handle_settings_click(self) -> None:
        if self._on_settings is not None:
            self._on_settings()

    def _handle_active_friends_changed(self, active_ids: list[str]) -> None:
        if self._on_active_friends_changed is not None:
            self._on_active_friends_changed(active_ids)

    def update_friends(
        self,
        friend_ids: list[str],
        active_friend_ids: list[str],
        cache: dict[str, FriendProfileSnapshot],
    ) -> None:
        self.friends_section.update_friends(friend_ids, active_friend_ids, cache)
