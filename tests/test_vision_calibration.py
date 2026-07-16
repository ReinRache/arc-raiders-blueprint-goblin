from arc_companion.vision.grid_calibration import (
    COLUMNS_PER_ROW,
    TOTAL_BLUEPRINTS,
    TOTAL_ROWS,
    blueprint_id_for_position,
    visible_rows_for_scroll,
)
from arc_companion.vision.import_merge import (
    EXPEDITION_REGRESSION_THRESHOLD,
    apply_full_reset,
    apply_upgrade_only,
    compute_merge_outcome,
    merge_found_ids,
    validate_pair,
)
from arc_companion.domain.status import BlueprintStatus, status_for


def test_position_formula_matches_verified_reference_matches():
    # Spot-verified against real reference-screenshot icons during planning.
    assert blueprint_id_for_position(1, 2) == 2  # Angled Grip III
    assert blueprint_id_for_position(1, 3) == 3  # Pulse Mine
    assert blueprint_id_for_position(1, 4) == 4  # Silencer II
    assert blueprint_id_for_position(1, 5) == 5  # Red Light Stick
    assert blueprint_id_for_position(1, 7) == 7  # Compensator II
    assert blueprint_id_for_position(1, 9) == 9  # Tactical Mk. 3 (Defensive)
    assert blueprint_id_for_position(2, 1) == 11  # Medium Gun Parts


def test_position_formula_has_no_exceptions_within_range():
    assert blueprint_id_for_position(1, 1) == 1


def test_position_formula_bounds_row_9_partial_columns():
    assert TOTAL_ROWS == 9
    assert blueprint_id_for_position(9, 3) == 83
    assert blueprint_id_for_position(9, 4) is None  # 84 > TOTAL_BLUEPRINTS


def test_position_formula_rejects_out_of_range_row_col():
    assert blueprint_id_for_position(0, 1) is None
    assert blueprint_id_for_position(10, 1) is None
    assert blueprint_id_for_position(1, 0) is None
    assert blueprint_id_for_position(1, COLUMNS_PER_ROW + 1) is None


def test_visible_rows_top_vs_bottom():
    top_rows = list(visible_rows_for_scroll(pinned_top=True))
    bottom_rows = list(visible_rows_for_scroll(pinned_top=False))
    assert top_rows == [1, 2, 3, 4, 5, 6]
    assert bottom_rows == [4, 5, 6, 7, 8, 9]
    assert bottom_rows[-1] == TOTAL_ROWS


def test_validate_pair_agrees_on_overlap():
    top = {1: True, 2: False, 3: True}
    bottom = {2: False, 3: True, 4: True}
    result = validate_pair(top, bottom)
    assert result.ok


def test_validate_pair_flags_disagreement():
    top = {1: True, 2: False}
    bottom = {2: True, 3: False}  # id 2 disagrees
    result = validate_pair(top, bottom)
    assert not result.ok
    assert "disagree" in result.error


def test_validate_pair_flags_no_overlap():
    result = validate_pair({1: True}, {50: False})
    assert not result.ok


def test_merge_found_ids_unions_true_values():
    top = {1: True, 2: False}
    bottom = {2: False, 3: True}
    assert merge_found_ids(top, bottom) == {1, 3}


def test_merge_outcome_upgrade_only_below_threshold():
    owned = {1, 2}
    wanted = {3}
    spare = set()
    scan_found = {1, 3}  # 2 goes missing (below threshold), 3 newly found
    outcome = compute_merge_outcome(scan_found, owned, wanted, spare)
    assert outcome.newly_found_ids == {3}
    assert outcome.regression_ids == {2}
    assert not outcome.needs_confirmation


def test_merge_outcome_needs_confirmation_at_threshold():
    owned = set(range(1, EXPEDITION_REGRESSION_THRESHOLD + 1))
    scan_found: set[int] = set()  # everything previously owned is now missing
    outcome = compute_merge_outcome(scan_found, owned, set(), set())
    assert len(outcome.regression_ids) == EXPEDITION_REGRESSION_THRESHOLD
    assert outcome.needs_confirmation


def test_apply_upgrade_only_never_downgrades():
    owned, wanted, spare = apply_upgrade_only({1}, {2}, set(), set())
    # id 2 (pre-existing OWNED) untouched, id 1 newly upgraded
    assert owned == {1, 2}


def test_apply_upgrade_only_does_not_touch_have():
    # HAVE id not present in newly_found_ids at all -> must stay HAVE
    owned = {5}
    spare = {5}
    owned, wanted, spare = apply_upgrade_only(set(), owned, set(), spare)
    assert status_for(5, owned, set(), spare) == BlueprintStatus.HAVE


def test_apply_full_reset_downgrades_missing_owned_but_preserves_have():
    owned = {1, 2, 3}
    spare = {3}  # id 3 is HAVE (superset of owned)
    scan_found: set[int] = set()  # nothing found in the new scan
    owned, wanted, spare = apply_full_reset(scan_found, owned, set(), spare)
    assert status_for(1, owned, wanted, spare) == BlueprintStatus.UNOWNED
    assert status_for(2, owned, wanted, spare) == BlueprintStatus.UNOWNED
    assert status_for(3, owned, wanted, spare) == BlueprintStatus.HAVE  # never downgraded


def test_apply_full_reset_upgrades_newly_found():
    owned, wanted, spare = apply_full_reset({7}, set(), set(), set())
    assert status_for(7, owned, wanted, spare) == BlueprintStatus.OWNED
