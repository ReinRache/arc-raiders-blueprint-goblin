import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, total_blueprints: int, **kwargs):
        super().__init__(master, corner_radius=0, **kwargs)
        self.total_blueprints = total_blueprints
        self.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(
            self,
            text="Arc Raiders\nBlueprint Goblin",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30), sticky="w")

        self.btn_my_blueprints = ctk.CTkButton(
            self, text="My Blueprints", fg_color="transparent", anchor="w"
        )
        self.btn_my_blueprints.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.owned_count_label = ctk.CTkLabel(
            self,
            text=f"Owned: 0/{total_blueprints}",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.owned_count_label.grid(row=1, column=0, padx=30, pady=5, sticky="e")

        # Placeholders for later phases (Steam sync, OCR import) — visible but inert
        self.btn_friends_directory = ctk.CTkButton(
            self,
            text="Steam Friends",
            fg_color="transparent",
            anchor="w",
            state="disabled",
        )
        self.btn_friends_directory.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_ocr_logs = ctk.CTkButton(
            self,
            text="OCR Logs & Settings",
            fg_color="transparent",
            anchor="w",
            state="disabled",
        )
        self.btn_ocr_logs.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

    def set_owned_count(self, owned: int) -> None:
        self.owned_count_label.configure(text=f"Owned: {owned}/{self.total_blueprints}")
