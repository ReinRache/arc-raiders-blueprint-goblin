import customtkinter as ctk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ArcRaidersGoblinApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 3) Rebranded App Window Title
        self.title("Arc Raiders Blueprint Goblin")
        self.geometry("1400x900")
        self.minsize(1000, 700)

        # ---------------------------------------------------------------------
        # Data Model Initialization (Tracking 83 items)
        # ---------------------------------------------------------------------
        # States: 0 = Unowned, 1 = Owned, 2 = Want, 3 = Have
        self.blueprint_data = []
        for i in range(83):
            self.blueprint_data.append({
                "id": i,
                "name": f"BP-{100 + i}",
                "state": 0  # Default to Unowned
            })

        # Track grid frame elements to clear/draw during filtering
        self.card_widgets = {}

        # ---------------------------------------------------------------------
        # Grid Configuration
        # ---------------------------------------------------------------------
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0, minsize=60)

        # ---------------------------------------------------------------------
        # 1. Navigation Sidebar
        # ---------------------------------------------------------------------
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # 3) Rebranded In-Window Corner Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Arc Raiders\nBlueprint Goblin", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30), sticky="w")

        # 2) Navigation Count Indicator Label
        self.btn_my_blueprints = ctk.CTkButton(
            self.sidebar_frame, text="My Blueprints", fg_color="transparent", anchor="w"
        )
        self.btn_my_blueprints.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.sidebar_count_lbl = ctk.CTkLabel(
            self.sidebar_frame, text="Owned: 0/83", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.sidebar_count_lbl.grid(row=1, column=0, padx=30, pady=5, sticky="e")

        # 4) Renamed to "Friends Directory" to align with Steam structure
        self.btn_friends_directory = ctk.CTkButton(
            self.sidebar_frame, text="Steam Friends", fg_color="transparent", anchor="w"
        )
        self.btn_friends_directory.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_ocr_logs = ctk.CTkButton(
            self.sidebar_frame, text="OCR Logs & Settings", fg_color="transparent", anchor="w"
        )
        self.btn_ocr_logs.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        # ---------------------------------------------------------------------
        # 2. Main Content Viewport
        # ---------------------------------------------------------------------
        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_view.grid_rowconfigure(2, weight=1) # Row 2 is the scroll frame now
        self.main_view.grid_columnconfigure(0, weight=1)

        # Container Header Layer
        self.header_frame = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(0, 15), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        # 2) Top Header Title Frame Tracker Display
        self.view_title = ctk.CTkLabel(
            self.header_frame, 
            text="Blueprint Database | 0/83 Collected", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.view_title.grid(row=0, column=0, sticky="w")

        # 1) Context Filtering Interactive Input Field Row
        self.filter_frame = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, pady=(0, 15), sticky="ew")
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.filter_grid)
        
        self.search_bar = ctk.CTkEntry(
            self.filter_frame, 
            placeholder_text="Search blueprint by name...", 
            textvariable=self.search_var,
            width=350
        )
        self.search_bar.grid(row=0, column=0, sticky="w")

        # Layout Content Dynamic Scroll Container Window
        self.scroll_content = ctk.CTkScrollableFrame(self.main_view)
        self.scroll_content.grid(row=2, column=0, sticky="nsew")
        
        for col in range(10):
            self.scroll_content.grid_columnconfigure(col, weight=1, pad=5)

        # Render elements the first time
        self.render_grid()
        self.update_count_displays()

        # ---------------------------------------------------------------------
        # 3. Bottom Action Bar
        # ---------------------------------------------------------------------
        self.action_bar = ctk.CTkFrame(self, height=60, corner_radius=0, border_width=1, border_color="#2A2A2A")
        self.action_bar.grid(row=1, column=1, sticky="ew")
        self.action_bar.grid_propagate(False)

        self.status_label = ctk.CTkLabel(self.action_bar, text="Cloud DB Status: Connected", text_color="#4CAF50")
        self.status_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # 5) Added Sync Database Button near server configuration indicators
        self.btn_sync = ctk.CTkButton(
            self.action_bar, text="Sync Changes", width=120, fg_color="#2B2B2B", border_width=1, border_color="#555555"
        )
        self.btn_sync.grid(row=0, column=1, padx=10, pady=15, sticky="w")

        self.btn_scan = ctk.CTkButton(self.action_bar, text="Scan Screenshot (OCR)", width=180)
        self.btn_scan.grid(row=0, column=2, padx=20, pady=15, sticky="e")
        
        self.action_bar.grid_columnconfigure(0, weight=0)
        self.action_bar.grid_columnconfigure(1, weight=1) # Standard pusher slot configuration

    def render_grid(self):
        """Draws cards to grid frame using tracked schema structures."""
        search_query = self.search_var.get().lower().strip()
        
        # Wipe old grid cards from layout window view completely
        for widget in self.card_widgets.values():
            widget.grid_forget()

        visible_index = 0
        for item in self.blueprint_data:
            # Check filter string conditions
            if search_query and search_query not in item["name"].lower():
                continue
                
            row = visible_index // 10
            col = visible_index % 10
            
            # Recalculate or construct card structure instance dynamically if needed
            if item["id"] not in self.card_widgets:
                card = ctk.CTkFrame(self.scroll_content, width=105, height=155, corner_radius=6)
                card.grid_propagate(False)
                
                img_standin = ctk.CTkFrame(card, width=75, height=75, fg_color="#1F538D", corner_radius=4)
                img_standin.grid(row=0, column=0, padx=15, pady=(10, 4))
                img_standin.grid_propagate(False)
                
                name_label = ctk.CTkLabel(
                    card, text=item["name"], font=ctk.CTkFont(size=11, weight="bold"), width=95, anchor="center"
                )
                name_label.grid(row=1, column=0, padx=5, pady=2)
                
                cycle_btn = ctk.CTkButton(
                    card, text="", font=ctk.CTkFont(size=10), height=20, width=85
                )
                cycle_btn.grid(row=2, column=0, padx=10, pady=(2, 8))
                cycle_btn.configure(command=lambda i=item["id"], b=cycle_btn: self.cycle_status(i, b))
                
                # Cache UI elements alongside properties references
                card.cycle_btn = cycle_btn
                self.card_widgets[item["id"]] = card

            # Visual properties layout configuration updates
            card = self.card_widgets[item["id"]]
            self.update_button_visuals(card.cycle_btn, item["state"])
            card.grid(row=row, column=col, padx=4, pady=8, sticky="nsew")
            
            visible_index += 1

    def cycle_status(self, item_id, button):
        """Transitions state step for the chosen layout data card item."""
        item = self.blueprint_data[item_id]
        item["state"] = (item["state"] + 1) % 4
        
        self.update_button_visuals(button, item["state"])
        self.update_count_displays()

    def update_button_visuals(self, button, state):
        """Changes style properties cleanly without reconstructing layout loops."""
        if state == 0:
            button.configure(text="Unowned", fg_color="#333333", hover_color="#444444")
        elif state == 1:
            button.configure(text="Owned", fg_color="#2E7D32", hover_color="#388E3C")
        elif state == 2:
            button.configure(text="Want", fg_color="#C62828", hover_color="#D32F2F")
        elif state == 3:
            button.configure(text="Have", fg_color="#1565C0", hover_color="#1976D2")

    def update_count_displays(self):
        """2) Calculates total owned checklist elements to format interface tracker windows."""
        # Only "Owned" (1) and "Have" (3, which implies you also secured one) count
        owned_count = sum(1 for item in self.blueprint_data if item["state"] in (1, 3))
        total = len(self.blueprint_data)
        
        self.view_title.configure(text=f"Blueprint Collection | {owned_count}/{total}")
        self.sidebar_count_lbl.configure(text=f"{owned_count}/{total}")

    def filter_grid(self, *args):
        """Triggered context update loop whenever text array configurations modify."""
        self.render_grid()

if __name__ == "__main__":
    app = ArcRaidersGoblinApp()
    app.mainloop()