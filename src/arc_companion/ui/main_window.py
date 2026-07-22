import dataclasses
import threading
import time

import customtkinter as ctk

from arc_companion.cloud.client import create_supabase_client
from arc_companion.cloud.friends import fetch_friend_profiles
from arc_companion.cloud.steam_proxy import get_player_summaries
from arc_companion.cloud.sync import ensure_session, push_profile
from arc_companion.data.blueprints import load_blueprints
from arc_companion.domain.friends import FriendStatusCounts, friend_status_counts_for, reconcile_active_friends
from arc_companion.domain.status import BlueprintStatus, apply_status, status_for
from arc_companion.storage.friends_cache import FriendProfileSnapshot, FriendsCacheStore
from arc_companion.storage.local_store import LocalJSONStore
from arc_companion.storage.supabase_session import SupabaseSessionStore
from arc_companion.ui.action_bar import ActionBar
from arc_companion.ui.blueprint_grid import CELL_SIZE, BlueprintGrid
from arc_companion.ui.manage_friends_dialog import ManageFriendsDialog
from arc_companion.ui.scan_dialog import ScanDialog
from arc_companion.ui.settings_dialog import SettingsDialog
from arc_companion.ui.sidebar import SIDEBAR_WIDTH, Sidebar
from arc_companion.ui.theme import ERROR_COLOR, SUCCESS_COLOR

# Non-sidebar portion of the gap between the window's width and the
# blueprint grid's actual usable (canvas) width: main_view horizontal
# padding (40px, 20 each side) + CTkScrollableFrame's vertical scrollbar
# (~16px) + a small internal border-radius allowance (~7px). Not derived
# from a formula CTk exposes — measured directly via winfo_width() at
# runtime. Keep this in sync if main_view padding changes below, or the
# "snug fit" window sizes will start showing slack again.
_NON_SIDEBAR_OVERHEAD_PX = 63
_GRID_OVERHEAD_PX = SIDEBAR_WIDTH + _NON_SIDEBAR_OVERHEAD_PX
_DEFAULT_COLUMNS = 10
_MIN_COLUMNS = 4


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Arc Raiders Blueprint Goblin")
        # Sized so the grid fits exactly _DEFAULT_COLUMNS/_MIN_COLUMNS cards
        # with no leftover slack on the right — confirmed via direct
        # winfo_width() measurement, not just computed (Tk's DPI widget
        # scaling and internal border spacing aren't reliably predictable
        # from constants alone).
        self.geometry(f"{_DEFAULT_COLUMNS * CELL_SIZE + _GRID_OVERHEAD_PX}x1080")
        self.minsize(_MIN_COLUMNS * CELL_SIZE + _GRID_OVERHEAD_PX, 700)

        self.store = LocalJSONStore()
        self.user_state = self.store.load_state()
        # load_state() generates a fresh arbg_user_id in memory on a brand-new
        # install (or migrates an old-format file) but doesn't write it back —
        # persist immediately so the identity is stable from the very first
        # launch, not regenerated on every run until some other save happens.
        self.store.save_state(self.user_state)
        self.owned_ids = set(self.user_state.blueprints_owned)
        self.wanted_ids = set(self.user_state.blueprints_wanted)
        self.spare_ids = set(self.user_state.blueprints_spare)

        self.blueprints = load_blueprints()
        self.total_blueprints = len(self.blueprints)

        # Creating the client is a local no-op (no network call) -- the
        # actual anonymous sign-in only happens lazily, inside ensure_session,
        # the first time the user clicks Sync or Wipe Cloud Data.
        self.cloud_client = create_supabase_client()
        self.cloud_session_store = SupabaseSessionStore()
        self._sync_in_flight = False

        # Cache read is local-disk, not network -- fine to do eagerly on
        # launch, unlike the actual cloud fetch (only ever triggered by Sync).
        self.friends_cache_store = FriendsCacheStore()
        self.friends_cache: dict[str, FriendProfileSnapshot] = self.friends_cache_store.load()

        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=60)

        self.sidebar = Sidebar(
            self,
            total_blueprints=self.total_blueprints,
            friend_ids=self.user_state.arbg_friend_user_ids,
            active_friend_ids=self.user_state.arbg_active_friend_ids,
            friends_cache=self.friends_cache,
            on_manage_friends=self._on_manage_friends_clicked,
            on_settings=self._on_settings_clicked,
            on_active_friends_changed=self._on_active_friends_changed,
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_view.grid_rowconfigure(2, weight=1)
        self.main_view.grid_columnconfigure(0, weight=1)

        self.header_frame = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(0, 15), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        # Split into multiple widgets (rather than one label string) because
        # "Copy ID" needs to be its own clickable widget.
        title_font = ctk.CTkFont(size=24, weight="bold")
        self.title_row = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.title_row.grid(row=0, column=0, sticky="w")

        self.title_prefix_label = ctk.CTkLabel(self.title_row, text="Blueprint Database | ", font=title_font)
        self.title_prefix_label.grid(row=0, column=0, sticky="w")

        # Its own label (not folded into the prefix string) so refreshing
        # just the name -- e.g. once a Steam persona name resolves after a
        # sync -- doesn't touch the surrounding layout.
        self.title_name_label = ctk.CTkLabel(self.title_row, text=self._display_name(), font=title_font)
        self.title_name_label.grid(row=0, column=1, sticky="w")

        # A real button, not a text hyperlink -- matches the "Copy" button
        # style already used in manage_friends_dialog.py's Goblin ID section
        # rather than the underlined-label link style used for the Steam API
        # key URL (that one opens an external page; this one is a same-app
        # action, closer in spirit to a normal button).
        self.title_copy_button = ctk.CTkButton(
            self.title_row, text="Copy ID", width=90, command=self._copy_own_id
        )
        self.title_copy_button.grid(row=0, column=2, padx=(8, 0), sticky="w")

        self.title_suffix_label = ctk.CTkLabel(
            self.title_row, text=self._collection_suffix(), font=title_font
        )
        self.title_suffix_label.grid(row=0, column=3, sticky="w")

        self.filter_frame = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, pady=(0, 15), sticky="ew")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_bar = ctk.CTkEntry(
            self.filter_frame,
            placeholder_text="Search blueprint by name...",
            textvariable=self.search_var,
            width=350,
        )
        self.search_bar.grid(row=0, column=0, sticky="w")

        self.grid_view = BlueprintGrid(
            self.main_view,
            blueprints=self.blueprints,
            status_for_id=self._status_for_id,
            on_cycle=self._on_cycle,
            friend_counts_for_id=self._friend_counts_for_id,
        )
        self.grid_view.grid(row=2, column=0, sticky="nsew")

        self.dirty = False
        self.action_bar = ActionBar(self, on_sync=self._on_sync_clicked, on_scan=self._on_scan_clicked)
        self.action_bar.grid(row=1, column=1, sticky="ew")
        self.action_bar.set_last_synced_at(self.user_state.last_synced_at)

    def _status_for_id(self, blueprint_id: int) -> BlueprintStatus:
        return status_for(blueprint_id, self.owned_ids, self.wanted_ids, self.spare_ids)

    def _friend_counts_for_id(self, blueprint_id: int) -> FriendStatusCounts:
        active_snapshots = [
            self.friends_cache[fid]
            for fid in self.user_state.arbg_active_friend_ids
            if fid in self.friends_cache
        ]
        return friend_status_counts_for(blueprint_id, active_snapshots)

    def _display_name(self) -> str:
        # Resolved via Steam's GetPlayerSummaries during Sync (Stage D), only
        # when Steam is linked and a Web API key is saved -- falls back to
        # the Goblin ID otherwise, same as before persona resolution existed.
        return self.user_state.steam_persona_name or self.user_state.arbg_user_id

    def _collection_suffix(self) -> str:
        return f" Collection {len(self.owned_ids)}/{self.total_blueprints}"

    def _copy_own_id(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.user_state.arbg_user_id)

    def _on_search_changed(self, *args) -> None:
        self.grid_view.set_search_query(self.search_var.get())

    def _on_cycle(self, blueprint_id: int) -> None:
        next_status = self._status_for_id(blueprint_id).next()
        self.owned_ids, self.wanted_ids, self.spare_ids = apply_status(
            blueprint_id, next_status, self.owned_ids, self.wanted_ids, self.spare_ids
        )
        self.user_state.blueprints_owned = sorted(self.owned_ids)
        self.user_state.blueprints_wanted = sorted(self.wanted_ids)
        self.user_state.blueprints_spare = sorted(self.spare_ids)
        # Local file write happens every click — cheap, and keeps progress durable
        # across crashes/restarts. This is separate from the (future) remote sync
        # below, which is the call we actually want to keep infrequent.
        self.store.save_state(self.user_state)

        self.grid_view.refresh_status(blueprint_id)
        self.title_suffix_label.configure(text=self._collection_suffix())

        self.dirty = True
        self.action_bar.set_dirty(True)

    def _on_sync_clicked(self) -> None:
        if self._sync_in_flight:
            return
        self._sync_in_flight = True
        self.action_bar.btn_sync.configure(state="disabled")
        self.action_bar.set_sync_status("Syncing & refreshing friends...", SUCCESS_COLOR)

        # Snapshot now, on the Tk thread, rather than reading self.user_state
        # from the background thread -- avoids pushing a state that's half
        # old/half new if the user clicks a card again while the network
        # call is in flight.
        state_snapshot = dataclasses.replace(self.user_state)

        def worker() -> None:
            try:
                user_id = ensure_session(self.cloud_client, self.cloud_session_store)
                push_profile(self.cloud_client, user_id, state_snapshot)
            except Exception:
                self.after(0, lambda: self._on_sync_finished(success=False))
                return

            # A friend-fetch failure shouldn't undo a successful push -- the
            # overlay just doesn't refresh this time, nothing is lost.
            friend_snapshots: dict[str, FriendProfileSnapshot] | None = None
            try:
                rows = fetch_friend_profiles(self.cloud_client, state_snapshot.arbg_friend_user_ids)
                friend_snapshots = {
                    row["arbg_user_id"]: FriendProfileSnapshot(
                        arbg_user_id=row["arbg_user_id"],
                        steam_id=row.get("steam_id"),
                        blueprints_owned=row.get("blueprints_owned", []),
                        blueprints_wanted=row.get("blueprints_wanted", []),
                        blueprints_spare=row.get("blueprints_spare", []),
                    )
                    for row in rows
                }
            except Exception:
                friend_snapshots = None

            # Persona-name resolution piggybacks on this same sync action --
            # no separate "Refresh Names" trigger. Skipped entirely (falls
            # back to Goblin ID everywhere) if there's nothing with a
            # steam_id to resolve. A resolution failure doesn't undo the
            # sync or the friend-data refresh above. No per-user Web API key
            # needed -- get_player_summaries goes through the shared Steam
            # proxy Edge Function (see cloud/steam_proxy.py), authenticated
            # by the same session ensure_session() already established above
            # for the push.
            resolved_own_name: str | None = None
            try:
                steam_ids_to_resolve = [
                    snap.steam_id for snap in (friend_snapshots or {}).values() if snap.steam_id
                ]
                if state_snapshot.steam_id:
                    steam_ids_to_resolve.append(state_snapshot.steam_id)
                if steam_ids_to_resolve:
                    names = get_player_summaries(self.cloud_client, steam_ids_to_resolve)
                    if friend_snapshots:
                        for snapshot in friend_snapshots.values():
                            if snapshot.steam_id in names:
                                snapshot.steam_name = names[snapshot.steam_id]
                    if state_snapshot.steam_id in names:
                        resolved_own_name = names[state_snapshot.steam_id]
            except Exception:
                resolved_own_name = None

            self.after(
                0,
                lambda: self._on_sync_finished(
                    success=True, friend_snapshots=friend_snapshots, resolved_own_name=resolved_own_name
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_sync_finished(
        self,
        success: bool,
        friend_snapshots: dict[str, FriendProfileSnapshot] | None = None,
        resolved_own_name: str | None = None,
    ) -> None:
        self._sync_in_flight = False
        if not success:
            self.action_bar.btn_sync.configure(state="normal")
            self.action_bar.set_sync_status("Sync failed — check your connection", ERROR_COLOR)
            return

        self.dirty = False
        self.action_bar.set_dirty(False)
        self.user_state.last_synced_at = int(time.time())
        if resolved_own_name is not None:
            self.user_state.steam_persona_name = resolved_own_name
        self.store.save_state(self.user_state)
        self.action_bar.set_last_synced_at(self.user_state.last_synced_at)
        self.action_bar.set_sync_status("Storage: Local + Cloud (Supabase) — Synced", SUCCESS_COLOR)
        self.title_name_label.configure(text=self._display_name())

        if friend_snapshots is not None:
            self.friends_cache = friend_snapshots
            self.friends_cache_store.save(self.friends_cache)
            self.grid_view.refresh_friend_overlay()
            self.sidebar.update_friends(
                self.user_state.arbg_friend_user_ids,
                self.user_state.arbg_active_friend_ids,
                self.friends_cache,
            )

    def _on_scan_clicked(self) -> None:
        ScanDialog(
            self,
            blueprints=self.blueprints,
            owned_ids=self.owned_ids,
            wanted_ids=self.wanted_ids,
            spare_ids=self.spare_ids,
            on_apply=self._apply_scan_result,
        )

    def _apply_scan_result(self, owned_ids: set[int], wanted_ids: set[int], spare_ids: set[int]) -> None:
        self.owned_ids, self.wanted_ids, self.spare_ids = owned_ids, wanted_ids, spare_ids
        self.user_state.blueprints_owned = sorted(self.owned_ids)
        self.user_state.blueprints_wanted = sorted(self.wanted_ids)
        self.user_state.blueprints_spare = sorted(self.spare_ids)
        self.store.save_state(self.user_state)

        # A scan can change many blueprints at once (unlike a single card
        # click), so refresh every existing card's status rather than just
        # one — still cheap, refresh_status() only recolors a label/button,
        # no icon reload or re-layout.
        for bp in self.blueprints:
            self.grid_view.refresh_status(bp.id)
        self.title_suffix_label.configure(text=self._collection_suffix())

        self.dirty = True
        self.action_bar.set_dirty(True)

    def _on_manage_friends_clicked(self) -> None:
        ManageFriendsDialog(
            self,
            arbg_user_id=self.user_state.arbg_user_id,
            steam_id=self.user_state.steam_id,
            friend_ids=self.user_state.arbg_friend_user_ids,
            on_friends_changed=self._on_friends_changed,
            on_steam_linked=self._on_steam_linked,
            cloud_client=self.cloud_client,
            cloud_session_store=self.cloud_session_store,
        )

    def _on_settings_clicked(self) -> None:
        SettingsDialog(self, cloud_client=self.cloud_client, cloud_session_store=self.cloud_session_store)

    def _on_friends_changed(self, friend_ids: list[str]) -> None:
        previous_friend_ids = self.user_state.arbg_friend_user_ids
        previous_active_ids = self.user_state.arbg_active_friend_ids
        self.user_state.arbg_friend_user_ids = friend_ids
        self.user_state.arbg_active_friend_ids = reconcile_active_friends(
            friend_ids, previous_friend_ids, previous_active_ids
        )
        # Drop any cache entry for a friend that's no longer in the roster --
        # matches the immediate-effect expectation from Settings' add/remove,
        # rather than waiting for the next sync to prune it.
        self.friends_cache = {fid: snap for fid, snap in self.friends_cache.items() if fid in friend_ids}
        self.friends_cache_store.save(self.friends_cache)
        self.store.save_state(self.user_state)

        self.sidebar.update_friends(
            self.user_state.arbg_friend_user_ids,
            self.user_state.arbg_active_friend_ids,
            self.friends_cache,
        )
        self.grid_view.refresh_friend_overlay()

    def _on_active_friends_changed(self, active_ids: list[str]) -> None:
        self.user_state.arbg_active_friend_ids = active_ids
        self.store.save_state(self.user_state)
        self.grid_view.refresh_friend_overlay()

    def _on_steam_linked(self, steam_id: str) -> None:
        self.user_state.steam_id = steam_id
        self.store.save_state(self.user_state)


def run() -> None:
    app = MainWindow()
    app.mainloop()
