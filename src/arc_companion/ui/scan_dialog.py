from collections.abc import Callable
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from arc_companion.data.blueprints import Blueprint
from arc_companion.vision import screenshot_reader as sr
from arc_companion.vision.import_merge import (
    MergeOutcome,
    apply_full_reset,
    apply_upgrade_only,
    compute_merge_outcome,
    merge_found_ids,
    validate_pair,
    validate_screenshot,
)
from arc_companion.ui.theme import (
    DESTRUCTIVE_COLOR,
    DESTRUCTIVE_HOVER_COLOR,
    ERROR_COLOR,
    NEUTRAL_BUTTON_COLOR,
    SUCCESS_COLOR_LIGHT,
    WARNING_COLOR,
)

_FILETYPES = [("PNG images", "*.png"), ("All files", "*.*")]


def _is_from_today(path: str) -> bool:
    # Soft heuristic — mtime can change on copy/transfer, isn't a hard
    # guarantee the screenshot itself is fresh, but catches the common case
    # of importing a stale file by mistake.
    mtime = Path(path).stat().st_mtime
    return date.fromtimestamp(mtime) == date.today()


class ScanDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        blueprints: list[Blueprint],
        owned_ids: set[int],
        wanted_ids: set[int],
        spare_ids: set[int],
        on_apply: Callable[[set[int], set[int], set[int]], None],
    ):
        super().__init__(master)
        self.title("Scan Collection Screenshots")
        self.geometry("560x360")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.blueprints_by_id = {bp.id: bp for bp in blueprints}
        self.owned_ids = owned_ids
        self.wanted_ids = wanted_ids
        self.spare_ids = spare_ids
        self.on_apply = on_apply

        self.top_grid: dict[int, bool] | None = None
        self.bottom_grid: dict[int, bool] | None = None
        self.merge_outcome: MergeOutcome | None = None
        self.scan_found_ids: set[int] = set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.step_label = ctk.CTkLabel(self, font=ctk.CTkFont(size=18, weight="bold"))
        self.step_label.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="w")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, padx=24, pady=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.grid(row=2, column=0, padx=24, pady=20, sticky="ew")
        self.nav_frame.grid_columnconfigure(0, weight=1)

        self._show_step1()

    # ---- Step 1: top screenshot -------------------------------------------------

    def _show_step1(self) -> None:
        self.step_label.configure(text="Step 1 of 2 — Top Screenshot")
        for widget in self.body.winfo_children():
            widget.destroy()
        for widget in self.nav_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.body,
            text="Scroll the in-game Blueprints panel all the way to the top, "
            "take a screenshot, then select it below.",
            wraplength=480,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(10, 20))

        ctk.CTkButton(self.body, text="Browse...", width=140, command=self._pick_top).grid(
            row=1, column=0, sticky="w"
        )

        self.step1_status = ctk.CTkLabel(self.body, text="", wraplength=480, justify="left")
        self.step1_status.grid(row=2, column=0, sticky="w", pady=(16, 0))

        self.step1_next_btn = ctk.CTkButton(
            self.nav_frame, text="Next", width=100, state="disabled", command=self._show_step2
        )
        self.step1_next_btn.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            self.nav_frame, text="Cancel", width=100, fg_color=NEUTRAL_BUTTON_COLOR, command=self.destroy
        ).grid(row=0, column=0, sticky="w")

    def _pick_top(self) -> None:
        path = filedialog.askopenfilename(title="Select the top screenshot", filetypes=_FILETYPES)
        if not path:
            return
        self._validate_and_report(path, expect_pinned_top=True, status_label=self.step1_status, next_btn=self.step1_next_btn, store_attr="top_grid")

    # ---- Step 2: bottom screenshot -----------------------------------------------

    def _show_step2(self) -> None:
        self.step_label.configure(text="Step 2 of 2 — Bottom Screenshot")
        for widget in self.body.winfo_children():
            widget.destroy()
        for widget in self.nav_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.body,
            text="Now scroll all the way to the bottom, take a second screenshot, "
            "and select it below.",
            wraplength=480,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(10, 20))

        ctk.CTkButton(self.body, text="Browse...", width=140, command=self._pick_bottom).grid(
            row=1, column=0, sticky="w"
        )

        self.step2_status = ctk.CTkLabel(self.body, text="", wraplength=480, justify="left")
        self.step2_status.grid(row=2, column=0, sticky="w", pady=(16, 0))

        self.step2_next_btn = ctk.CTkButton(
            self.nav_frame, text="Review", width=100, state="disabled", command=self._show_review
        )
        self.step2_next_btn.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            self.nav_frame, text="Back", width=100, fg_color=NEUTRAL_BUTTON_COLOR, command=self._show_step1
        ).grid(row=0, column=0, sticky="w")

    def _pick_bottom(self) -> None:
        path = filedialog.askopenfilename(title="Select the bottom screenshot", filetypes=_FILETYPES)
        if not path:
            return
        self._validate_and_report(path, expect_pinned_top=False, status_label=self.step2_status, next_btn=self.step2_next_btn, store_attr="bottom_grid")

    # ---- shared per-screenshot validation ----------------------------------------

    def _validate_and_report(
        self, path: str, expect_pinned_top: bool, status_label: ctk.CTkLabel, next_btn: ctk.CTkButton, store_attr: str
    ) -> None:
        messages = []
        if not _is_from_today(path):
            captured = date.fromtimestamp(Path(path).stat().st_mtime)
            messages.append(f"⚠ This file looks like it's from {captured}, not today — make sure it's a fresh screenshot.")

        image = sr.load_image(path)
        result = validate_screenshot(image, expect_pinned_top=expect_pinned_top)
        if not result.ok:
            status_label.configure(text="\n".join([*messages, f"✗ {result.error}"]), text_color=ERROR_COLOR)
            next_btn.configure(state="disabled")
            setattr(self, store_attr, None)
            return

        if store_attr == "bottom_grid" and self.top_grid is not None:
            pair_result = validate_pair(self.top_grid, result.grid_result)
            if not pair_result.ok:
                status_label.configure(
                    text="\n".join([*messages, f"✗ {pair_result.error}"]), text_color=ERROR_COLOR
                )
                next_btn.configure(state="disabled")
                setattr(self, store_attr, None)
                return

        setattr(self, store_attr, result.grid_result)
        messages.append("✓ Looks good.")
        status_label.configure(text="\n".join(messages), text_color=SUCCESS_COLOR_LIGHT)
        next_btn.configure(state="normal")

    # ---- Step 3: review + apply ---------------------------------------------------

    def _show_review(self) -> None:
        assert self.top_grid is not None and self.bottom_grid is not None
        self.scan_found_ids = merge_found_ids(self.top_grid, self.bottom_grid)
        self.merge_outcome = compute_merge_outcome(
            self.scan_found_ids, self.owned_ids, self.wanted_ids, self.spare_ids
        )

        self.step_label.configure(text="Review")
        for widget in self.body.winfo_children():
            widget.destroy()
        for widget in self.nav_frame.winfo_children():
            widget.destroy()

        newly_found = self.merge_outcome.newly_found_ids
        if newly_found:
            names = ", ".join(
                sorted(self.blueprints_by_id[bid].name for bid in newly_found if bid in self.blueprints_by_id)
            )
            summary = f"{len(newly_found)} new blueprint(s) found:\n{names}"
        else:
            summary = "No new blueprints found in this scan."
        ctk.CTkLabel(self.body, text=summary, wraplength=480, justify="left").grid(
            row=0, column=0, sticky="w", pady=(10, 10)
        )

        if self.merge_outcome.needs_confirmation:
            regression_names = ", ".join(
                sorted(
                    self.blueprints_by_id[bid].name
                    for bid in self.merge_outcome.regression_ids
                    if bid in self.blueprints_by_id
                )
            )
            ctk.CTkLabel(
                self.body,
                text=(
                    f"This scan shows {len(self.merge_outcome.regression_ids)} blueprint(s) you'd "
                    f"marked as owned no longer found:\n{regression_names}\n\n"
                    "If you went on an Expedition, you can apply this scan as your new full "
                    "collection state (marks those as unowned too). Otherwise we'll just add "
                    "what's newly found and leave the rest alone."
                ),
                wraplength=480,
                justify="left",
                text_color=WARNING_COLOR,
            ).grid(row=1, column=0, sticky="w", pady=(0, 10))

            ctk.CTkButton(
                self.nav_frame,
                text="Apply as Expedition Reset",
                width=200,
                fg_color=DESTRUCTIVE_COLOR,
                hover_color=DESTRUCTIVE_HOVER_COLOR,
                command=self._apply_full_reset,
            ).grid(row=0, column=1, sticky="e", padx=(8, 0))
            ctk.CTkButton(
                self.nav_frame, text="Just Add New", width=140, command=self._apply_upgrade_only
            ).grid(row=0, column=2, sticky="e")
        else:
            ctk.CTkButton(
                self.nav_frame, text="Apply", width=120, command=self._apply_upgrade_only
            ).grid(row=0, column=2, sticky="e")

        ctk.CTkButton(
            self.nav_frame, text="Back", width=100, fg_color=NEUTRAL_BUTTON_COLOR, command=self._show_step2
        ).grid(row=0, column=0, sticky="w")

    def _apply_upgrade_only(self) -> None:
        owned, wanted, spare = apply_upgrade_only(
            self.merge_outcome.newly_found_ids, self.owned_ids, self.wanted_ids, self.spare_ids
        )
        self.on_apply(owned, wanted, spare)
        self.destroy()

    def _apply_full_reset(self) -> None:
        owned, wanted, spare = apply_full_reset(
            self.scan_found_ids, self.owned_ids, self.wanted_ids, self.spare_ids
        )
        self.on_apply(owned, wanted, spare)
        self.destroy()
