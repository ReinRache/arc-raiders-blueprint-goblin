from dataclasses import dataclass, field

import numpy as np

from arc_companion.domain.status import BlueprintStatus, apply_status, status_for
from arc_companion.vision import screenshot_reader as sr

# Comfortably more than "one or two cells misread" — at/above this many
# previously-owned blueprints going missing in a scan looks like a real
# progression wipe ("Expedition" in-game) rather than a bad screenshot.
EXPEDITION_REGRESSION_THRESHOLD = 5


@dataclass
class ValidationResult:
    ok: bool
    error: str | None = None
    grid_result: dict[int, bool] = field(default_factory=dict)


def validate_screenshot(image: np.ndarray, expect_pinned_top: bool) -> ValidationResult:
    """Validates a single screenshot (panel detected + scrollbar pinned in the
    expected direction) and reads its grid if valid."""
    if not sr.find_panel(image):
        return ValidationResult(
            ok=False,
            error="Doesn't look like the Blueprints panel screenshot (wrong size, or the panel wasn't found).",
        )
    pinned = sr.is_pinned_top(image) if expect_pinned_top else sr.is_pinned_bottom(image)
    if not pinned:
        direction = "top" if expect_pinned_top else "bottom"
        return ValidationResult(
            ok=False,
            error=f"The scrollbar isn't all the way at the {direction} — scroll fully to the {direction} before taking this screenshot.",
        )
    return ValidationResult(ok=True, grid_result=sr.read_grid(image, pinned_top=expect_pinned_top))


def validate_pair(top_grid: dict[int, bool], bottom_grid: dict[int, bool]) -> ValidationResult:
    """Cross-checks the row(s) shared between a validated top and bottom
    screenshot — this is the actual "two screenshots agree" check, catching
    e.g. screenshots from different accounts/sessions without needing to
    read the "FOUND: X/83" counter text."""
    shared_ids = set(top_grid) & set(bottom_grid)
    if not shared_ids:
        return ValidationResult(
            ok=False,
            error="These two screenshots don't share any rows — make sure both are from the same Blueprints panel, scrolled fully to opposite ends.",
        )
    mismatches = {bid for bid in shared_ids if top_grid[bid] != bottom_grid[bid]}
    if mismatches:
        return ValidationResult(
            ok=False,
            error=f"The two screenshots disagree on {len(mismatches)} shared blueprint(s) — make sure both are from the same account and a recent capture.",
        )
    return ValidationResult(ok=True)


def merge_found_ids(top_grid: dict[int, bool], bottom_grid: dict[int, bool]) -> set[int]:
    merged = {**top_grid, **bottom_grid}
    return {bid for bid, found in merged.items() if found}


@dataclass
class MergeOutcome:
    newly_found_ids: set[int]
    regression_ids: set[int]

    @property
    def needs_confirmation(self) -> bool:
        return len(self.regression_ids) >= EXPEDITION_REGRESSION_THRESHOLD


def compute_merge_outcome(
    scan_found_ids: set[int], owned_ids: set[int], wanted_ids: set[int], spare_ids: set[int]
) -> MergeOutcome:
    newly_found = {
        bid
        for bid in scan_found_ids
        if status_for(bid, owned_ids, wanted_ids, spare_ids) in (BlueprintStatus.UNOWNED, BlueprintStatus.WANT)
    }
    # owned_ids already includes HAVE ids (apply_status adds HAVE to both
    # owned_ids and spare_ids), so this alone is the full "you have it" set.
    regression_ids = owned_ids - scan_found_ids
    return MergeOutcome(newly_found_ids=newly_found, regression_ids=regression_ids)


def apply_upgrade_only(
    newly_found_ids: set[int], owned_ids: set[int], wanted_ids: set[int], spare_ids: set[int]
) -> tuple[set[int], set[int], set[int]]:
    for blueprint_id in newly_found_ids:
        owned_ids, wanted_ids, spare_ids = apply_status(
            blueprint_id, BlueprintStatus.OWNED, owned_ids, wanted_ids, spare_ids
        )
    return owned_ids, wanted_ids, spare_ids


def apply_full_reset(
    scan_found_ids: set[int], owned_ids: set[int], wanted_ids: set[int], spare_ids: set[int]
) -> tuple[set[int], set[int], set[int]]:
    """Treats the scan as the new authoritative collection state (the user
    confirmed this after an Expedition-regression prompt). HAVE blueprints
    are never touched either direction — a spare copy is a fact the
    Blueprints panel doesn't show at all, so a scan has no way to confirm or
    deny it; only OWNED (not HAVE) ids get downgraded to UNOWNED here."""
    for blueprint_id in list(owned_ids):
        if status_for(blueprint_id, owned_ids, wanted_ids, spare_ids) == BlueprintStatus.HAVE:
            continue
        if blueprint_id not in scan_found_ids:
            owned_ids, wanted_ids, spare_ids = apply_status(
                blueprint_id, BlueprintStatus.UNOWNED, owned_ids, wanted_ids, spare_ids
            )
    # Re-filter to UNOWNED/WANT only (as apply_upgrade_only expects) — passing
    # scan_found_ids straight through here would re-downgrade any HAVE id
    # that's also found in this scan back down to plain OWNED.
    newly_found = {
        bid
        for bid in scan_found_ids
        if status_for(bid, owned_ids, wanted_ids, spare_ids) in (BlueprintStatus.UNOWNED, BlueprintStatus.WANT)
    }
    return apply_upgrade_only(newly_found, owned_ids, wanted_ids, spare_ids)
