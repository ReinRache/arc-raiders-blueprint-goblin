from arc_companion.domain.status import BlueprintStatus, apply_status, status_for


def test_next_wraps_through_all_four_states():
    assert BlueprintStatus.UNOWNED.next() == BlueprintStatus.WANT
    assert BlueprintStatus.WANT.next() == BlueprintStatus.OWNED
    assert BlueprintStatus.OWNED.next() == BlueprintStatus.HAVE
    assert BlueprintStatus.HAVE.next() == BlueprintStatus.UNOWNED


def test_status_for_reads_from_the_right_set():
    assert status_for(1, set(), set(), set()) == BlueprintStatus.UNOWNED
    assert status_for(1, {1}, set(), set()) == BlueprintStatus.OWNED
    assert status_for(1, set(), {1}, set()) == BlueprintStatus.WANT
    assert status_for(1, set(), set(), {1}) == BlueprintStatus.HAVE


def test_status_for_have_wins_even_if_also_wanted():
    # spare (HAVE) takes priority; a blueprint can't simultaneously be "wanted"
    # in practice once you have a spare, but the lookup should still be well-defined
    assert status_for(1, set(), {1}, {1}) == BlueprintStatus.HAVE


def test_apply_status_have_also_sets_owned_for_collection_accounting():
    owned, wanted, spare = apply_status(1, BlueprintStatus.HAVE, set(), set(), set())
    assert owned == {1}
    assert spare == {1}
    assert wanted == set()


def test_apply_status_want_does_not_set_owned():
    owned, wanted, spare = apply_status(1, BlueprintStatus.WANT, set(), set(), set())
    assert owned == set()
    assert wanted == {1}
    assert spare == set()


def test_apply_status_unowned_clears_all_three_sets():
    owned, wanted, spare = apply_status(1, BlueprintStatus.UNOWNED, {1}, {1}, {1})
    assert owned == set()
    assert wanted == set()
    assert spare == set()


def test_apply_status_only_touches_the_target_id():
    owned, wanted, spare = apply_status(1, BlueprintStatus.OWNED, {2}, {3}, {4})
    assert owned == {1, 2}
    assert wanted == {3}
    assert spare == {4}
