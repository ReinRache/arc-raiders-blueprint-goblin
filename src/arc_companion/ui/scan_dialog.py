from collections.abc import Callable
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from arc_companion.data.blueprints import CATEGORIES, CATEGORY_LABELS, Blueprint
from arc_companion.data.layouts import load_layout
from arc_companion.ui.theme import (
    DESTRUCTIVE_COLOR,
    DESTRUCTIVE_HOVER_COLOR,
    ERROR_COLOR,
    NEUTRAL_BUTTON_COLOR,
    SUCCESS_COLOR_LIGHT,
    WARNING_COLOR,
)
from arc_companion.vision import screenshot_reader as sr
from arc_companion.vision.import_merge import (
    MergeOutcome,
    apply_full_reset,
    apply_upgrade_only,
    compute_merge_outcome,
    validate_panel_screenshot,
)
from arc_companion.vision.static_panel import StaticPanelSpec, load_static_specs

_FILETYPES = [("PNG images", "*.png"), ("All files", "*.*")]
# Long name lists in the review would overflow the fixed-size dialog.
_MAX_NAMES_SHOWN = 12


def _is_from_today(path: str) -> bool:
    # Soft heuristic — mtime can change on copy/transfer, isn't a hard
    # guarantee the screenshot itself is fresh, but catches the common case
    # of importing a stale file by mistake.
    mtime = Path(path).stat().st_mtime
    return date.fromtimestamp(mtime) == date.today()


def _names(items_by_id: dict[int, Blueprint], ids: set[int]) -> str:
    names = sorted(items_by_id[i].name for i in ids if i in items_by_id)
    shown = ", ".join(names[:_MAX_NAMES_SHOWN])
    return shown + (f" … and {len(names) - _MAX_NAMES_SHOWN} more" if len(names) > _MAX_NAMES_SHOWN else "")


class ScanDialog(ctk.CTkToplevel):
    """Imports collection progress from screenshots. Since the Frozen Trail
    update each tab (Blueprints / Stencils / Designs) is one non-scrolling
    grid, so it's one full-window screenshot per tab -- and any subset of the
    three can be scanned (a scan only ever touches the tabs you gave it)."""

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
        self.geometry("620x500")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.blueprints_by_id = {bp.id: bp for bp in blueprints}
        self.owned_ids = owned_ids
        self.wanted_ids = wanted_ids
        self.spare_ids = spare_ids
        self.on_apply = on_apply

        self.specs: dict[str, StaticPanelSpec] = load_static_specs()
        known = set(self.blueprints_by_id)
        self.layouts: dict[str, list[int]] = {c: load_layout(c, known_ids=known) for c in CATEGORIES}
        # category -> {item_id: found} for each tab with a validated screenshot
        self.grids: dict[str, dict[int, bool]] = {}
        self.scan_found_ids: set[int] = set()
        self.scope_ids: set[int] = set()
        self.merge_outcome: MergeOutcome | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.step_label = ctk.CTkLabel(self, font=ctk.CTkFont(size=18, weight="bold"))
        self.step_label.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="w")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, padx=24, pady=0, sticky="nsew")
        self.body.grid_columnconfigure(1, weight=1)

        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.grid(row=2, column=0, padx=24, pady=20, sticky="ew")
        self.nav_frame.grid_columnconfigure(0, weight=1)

        self._show_pick_step()

    # ---- Step 1: one screenshot per tab -------------------------------------------

    def _clear(self) -> None:
        for widget in self.body.winfo_children():
            widget.destroy()
        for widget in self.nav_frame.winfo_children():
            widget.destroy()

    def _show_pick_step(self) -> None:
        self.step_label.configure(text="Choose your screenshots")
        self._clear()

        ctk.CTkLabel(
            self.body,
            text="Open the Collections screen in-game. For each tab you want to import, switch to "
            "that tab and take a full-window screenshot of the Arc Raiders viewport (not a cropped "
            "or partial capture), saved as a PNG. Then pick the file for that tab below — "
            "you only need the tabs you want to update.",
            wraplength=560,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        self._status_labels: dict[str, ctk.CTkLabel] = {}
        for row, category in enumerate(CATEGORIES, start=1):
            ctk.CTkLabel(self.body, text=CATEGORY_LABELS[category], font=ctk.CTkFont(weight="bold")).grid(
                row=row, column=0, sticky="nw", pady=(8, 0), padx=(0, 14)
            )
            spec = self.specs.get(category)
            enabled = spec is not None and spec.enabled
            ctk.CTkButton(
                self.body,
                text="Browse..." if enabled else "Coming soon",
                width=110,
                state="normal" if enabled else "disabled",
                command=lambda c=category: self._pick(c),
            ).grid(row=row, column=1, sticky="nw", pady=(8, 0))
            label = ctk.CTkLabel(
                self.body,
                text=self._summary_for(category),
                wraplength=380,
                justify="left",
                text_color="gray" if category not in self.grids else SUCCESS_COLOR_LIGHT,
            )
            label.grid(row=row, column=2, sticky="nw", padx=(14, 0), pady=(10, 0))
            self._status_labels[category] = label

        self.review_btn = ctk.CTkButton(
            self.nav_frame,
            text="Review",
            width=100,
            state="normal" if self.grids else "disabled",
            command=self._show_review,
        )
        self.review_btn.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            self.nav_frame, text="Cancel", width=100, fg_color=NEUTRAL_BUTTON_COLOR, command=self.destroy
        ).grid(row=0, column=0, sticky="w")

    def _summary_for(self, category: str) -> str:
        grid = self.grids.get(category)
        if grid is None:
            return "No screenshot chosen."
        return f"✓ Looks good — {sum(grid.values())} of {len(grid)} tiles found."

    def _pick(self, category: str) -> None:
        label = CATEGORY_LABELS[category]
        path = filedialog.askopenfilename(title=f"Select the {label} screenshot", filetypes=_FILETYPES)
        if not path:
            return
        self._validate_and_report(path, category)

    def _validate_and_report(self, path: str, category: str) -> None:
        status = self._status_labels[category]
        notes = []
        if not _is_from_today(path):
            captured = date.fromtimestamp(Path(path).stat().st_mtime)
            notes.append(f"⚠ This file looks like it's from {captured}, not today — make sure it's a fresh screenshot.")

        try:
            image = sr.load_image(path)
        except Exception:
            status.configure(text="✗ Couldn't open that file as an image.", text_color=ERROR_COLOR)
            self.grids.pop(category, None)
            self._refresh_review_button()
            return

        result = validate_panel_screenshot(image, category, self.specs[category], self.layouts[category])
        if not result.ok:
            status.configure(text="\n".join([*notes, f"✗ {result.error}"]), text_color=ERROR_COLOR)
            self.grids.pop(category, None)
        else:
            self.grids[category] = result.grid_result
            status.configure(text="\n".join([*notes, self._summary_for(category)]), text_color=SUCCESS_COLOR_LIGHT)
        self._refresh_review_button()

    def _refresh_review_button(self) -> None:
        self.review_btn.configure(state="normal" if self.grids else "disabled")

    # ---- Step 2: review + apply ---------------------------------------------------

    def _show_review(self) -> None:
        # Only the tabs actually scanned are in scope: an item on a tab the
        # user didn't scan must never count as "missing from the scan".
        self.scan_found_ids = {i for grid in self.grids.values() for i, found in grid.items() if found}
        self.scope_ids = {i for category in self.grids for i in self.layouts[category]}
        self.merge_outcome = compute_merge_outcome(
            self.scan_found_ids, self.owned_ids, self.wanted_ids, self.spare_ids, scope_ids=self.scope_ids
        )

        self.step_label.configure(text="Review")
        self._clear()
        self.body.grid_columnconfigure(0, weight=1)

        newly_found = self.merge_outcome.newly_found_ids
        scanned = ", ".join(CATEGORY_LABELS[c] for c in CATEGORIES if c in self.grids)
        if newly_found:
            summary = f"Scanned: {scanned}.\n{len(newly_found)} newly found:\n{_names(self.blueprints_by_id, newly_found)}"
        else:
            summary = f"Scanned: {scanned}.\nNothing new found in this scan."
        ctk.CTkLabel(self.body, text=summary, wraplength=570, justify="left").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        if self.merge_outcome.needs_confirmation:
            ctk.CTkLabel(
                self.body,
                text=(
                    f"This scan shows {len(self.merge_outcome.regression_ids)} item(s) you'd marked as "
                    f"owned no longer found:\n{_names(self.blueprints_by_id, self.merge_outcome.regression_ids)}\n\n"
                    "If you went on an Expedition, you can apply this scan as your new full "
                    "collection state for the scanned tabs (marks those as unowned too). "
                    "Otherwise we'll just add what's newly found and leave the rest alone."
                ),
                wraplength=570,
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
            self.nav_frame, text="Back", width=100, fg_color=NEUTRAL_BUTTON_COLOR, command=self._back_to_pick
        ).grid(row=0, column=0, sticky="w")

    def _back_to_pick(self) -> None:
        self.body.grid_columnconfigure(0, weight=0)
        self._show_pick_step()

    def _apply_upgrade_only(self) -> None:
        owned, wanted, spare = apply_upgrade_only(
            self.merge_outcome.newly_found_ids, self.owned_ids, self.wanted_ids, self.spare_ids
        )
        self.on_apply(owned, wanted, spare)
        self.destroy()

    def _apply_full_reset(self) -> None:
        owned, wanted, spare = apply_full_reset(
            self.scan_found_ids, self.owned_ids, self.wanted_ids, self.spare_ids, scope_ids=self.scope_ids
        )
        self.on_apply(owned, wanted, spare)
        self.destroy()
