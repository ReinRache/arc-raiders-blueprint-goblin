from collections.abc import Callable

import customtkinter as ctk
from PIL import Image

from arc_companion.data.blueprints import Blueprint

_ICON_SIZE = (48, 48)


class BlueprintGrid(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        blueprints: list[Blueprint],
        owned_ids: set[int],
        on_toggle: Callable[[int, bool], None],
        **kwargs,
    ):
        super().__init__(master, label_text="Blueprints", **kwargs)
        self.on_toggle = on_toggle
        self._icons = {}  # keep CTkImage refs alive; Tk garbage-collects images with no referrer

        for row, bp in enumerate(blueprints):
            self._build_row(row, bp, owned=bp.id in owned_ids)

    def _build_row(self, row: int, bp: Blueprint, owned: bool) -> None:
        icon = self._load_icon(bp)
        if icon is not None:
            icon_label = ctk.CTkLabel(self, image=icon, text="")
            icon_label.grid(row=row, column=0, padx=(4, 8), pady=4)

        name_label = ctk.CTkLabel(self, text=bp.name, anchor="w")
        name_label.grid(row=row, column=1, sticky="w", padx=(0, 8), pady=4)

        var = ctk.BooleanVar(value=owned)
        checkbox = ctk.CTkCheckBox(
            self,
            text="Owned",
            variable=var,
            command=lambda bp_id=bp.id, v=var: self.on_toggle(bp_id, v.get()),
        )
        checkbox.grid(row=row, column=2, sticky="e", padx=4, pady=4)

    def _load_icon(self, bp: Blueprint):
        if not bp.image_path.exists():
            return None
        image = Image.open(bp.image_path).convert("RGBA")
        icon = ctk.CTkImage(light_image=image, dark_image=image, size=_ICON_SIZE)
        self._icons[bp.id] = icon
        return icon
