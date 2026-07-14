import customtkinter as ctk

from arc_companion.data.blueprints import load_blueprints
from arc_companion.storage.local_store import LOCAL_USER_ID, LocalJSONStore
from arc_companion.ui.blueprint_grid import BlueprintGrid


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Arc Raiders Blueprint Tracker")
        self.geometry("900x700")

        self.store = LocalJSONStore()
        self.user_state = self.store.load_state(LOCAL_USER_ID)
        blueprints = load_blueprints()

        self.grid_view = BlueprintGrid(
            self,
            blueprints=blueprints,
            owned_ids=set(self.user_state.blueprints_owned),
            on_toggle=self._on_toggle,
        )
        self.grid_view.pack(fill="both", expand=True, padx=12, pady=12)

    def _on_toggle(self, blueprint_id: int, owned: bool) -> None:
        owned_set = set(self.user_state.blueprints_owned)
        if owned:
            owned_set.add(blueprint_id)
        else:
            owned_set.discard(blueprint_id)
        self.user_state.blueprints_owned = sorted(owned_set)
        self.store.save_state(self.user_state)


def run() -> None:
    app = MainWindow()
    app.mainloop()
