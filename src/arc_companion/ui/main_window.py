import customtkinter as ctk

from arc_companion.data.blueprints import load_blueprints
from arc_companion.domain.status import BlueprintStatus, apply_status, status_for
from arc_companion.storage.local_store import LOCAL_USER_ID, LocalJSONStore
from arc_companion.ui.action_bar import ActionBar
from arc_companion.ui.blueprint_grid import CELL_SIZE, BlueprintGrid
from arc_companion.ui.sidebar import Sidebar

# Gap between the window's width and the blueprint grid's actual usable
# (canvas) width: sidebar (220px, set below) + main_view horizontal padding
# (40px, 20 each side) + CTkScrollableFrame's vertical scrollbar (~16px) + a
# small internal border-radius allowance (~7px). Not derived from a formula
# CTk exposes — measured directly via winfo_width() at runtime. Keep this in
# sync if the sidebar width or main_view padding changes below, or the
# "snug fit" window sizes will start showing slack again.
_GRID_OVERHEAD_PX = 283
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
        self.user_state = self.store.load_state(LOCAL_USER_ID)
        self.owned_ids = set(self.user_state.blueprints_owned)
        self.wanted_ids = set(self.user_state.blueprints_wanted)
        self.spare_ids = set(self.user_state.blueprints_spare)

        self.blueprints = load_blueprints()
        self.total_blueprints = len(self.blueprints)

        self.grid_columnconfigure(0, weight=0, minsize=220)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=60)

        self.sidebar = Sidebar(self, total_blueprints=self.total_blueprints)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_view.grid_rowconfigure(2, weight=1)
        self.main_view.grid_columnconfigure(0, weight=1)

        self.header_frame = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(0, 15), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.view_title = ctk.CTkLabel(
            self.header_frame,
            text=self._header_text(),
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.view_title.grid(row=0, column=0, sticky="w")

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
        )
        self.grid_view.grid(row=2, column=0, sticky="nsew")

        self.dirty = False
        self.action_bar = ActionBar(self, on_sync=self._on_sync_clicked)
        self.action_bar.grid(row=1, column=1, sticky="ew")

    def _status_for_id(self, blueprint_id: int) -> BlueprintStatus:
        return status_for(blueprint_id, self.owned_ids, self.wanted_ids, self.spare_ids)

    def _header_text(self) -> str:
        return f"Blueprint Database | {len(self.owned_ids)}/{self.total_blueprints} Collected"

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
        self.view_title.configure(text=self._header_text())
        self.sidebar.set_owned_count(len(self.owned_ids))

        self.dirty = True
        self.action_bar.set_dirty(True)

    def _on_sync_clicked(self) -> None:
        # No remote store exists yet (Phase 3 adds one). For now this just
        # acknowledges the pending local changes so the button dims again;
        # once there's a cloud Store this is where the actual push call goes.
        self.dirty = False
        self.action_bar.set_dirty(False)


def run() -> None:
    app = MainWindow()
    app.mainloop()
