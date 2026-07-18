from arc_companion.domain.friends import (
    FriendStatusCounts,
    Highlight,
    compute_highlight,
    discoverable_steam_friends,
    friend_status_counts_for,
    reconcile_active_friends,
    visible_friend_ids,
)
from arc_companion.domain.status import BlueprintStatus
from arc_companion.storage.friends_cache import FriendProfileSnapshot

# ---- friend_status_counts_for -------------------------------------------------


def test_friend_status_counts_for_buckets_each_friend():
    friends = [
        FriendProfileSnapshot(arbg_user_id="A", blueprints_spare=[1]),
        FriendProfileSnapshot(arbg_user_id="B", blueprints_wanted=[1]),
        FriendProfileSnapshot(arbg_user_id="C", blueprints_owned=[1]),
        FriendProfileSnapshot(arbg_user_id="D"),
    ]
    counts = friend_status_counts_for(1, friends)
    assert counts.have == ["A"]
    assert counts.want == ["B"]
    assert counts.owned == ["C"]
    assert counts.unowned == ["D"]


def test_friend_status_counts_for_empty_snapshots():
    counts = friend_status_counts_for(1, [])
    assert counts.have == counts.want == counts.owned == counts.unowned == []


def test_friend_status_counts_for_only_considers_given_blueprint():
    friends = [FriendProfileSnapshot(arbg_user_id="A", blueprints_spare=[2])]
    counts = friend_status_counts_for(1, friends)
    assert counts.unowned == ["A"]
    assert counts.have == []


# ---- compute_highlight ----------------------------------------------------------


def test_highlight_want_with_friend_have_is_thick_green():
    counts = FriendStatusCounts(have=["A"])
    assert compute_highlight(BlueprintStatus.WANT, counts) == Highlight.THICK_GREEN


def test_highlight_want_without_friend_have_is_none():
    counts = FriendStatusCounts(want=["A"], owned=["B"])
    assert compute_highlight(BlueprintStatus.WANT, counts) == Highlight.NONE


def test_highlight_unowned_with_friend_have_is_thin_green():
    counts = FriendStatusCounts(have=["A"])
    assert compute_highlight(BlueprintStatus.UNOWNED, counts) == Highlight.THIN_GREEN


def test_highlight_unowned_without_friend_have_is_none():
    counts = FriendStatusCounts(want=["A"])
    assert compute_highlight(BlueprintStatus.UNOWNED, counts) == Highlight.NONE


def test_highlight_have_with_friend_want_is_thick_cyan():
    counts = FriendStatusCounts(want=["A"], unowned=["B"])
    assert compute_highlight(BlueprintStatus.HAVE, counts) == Highlight.THICK_CYAN


def test_highlight_have_with_only_friend_unowned_is_thin_cyan():
    counts = FriendStatusCounts(unowned=["A"])
    assert compute_highlight(BlueprintStatus.HAVE, counts) == Highlight.THIN_CYAN


def test_highlight_have_with_no_matching_friend_status_is_none():
    counts = FriendStatusCounts(have=["A"], owned=["B"])
    assert compute_highlight(BlueprintStatus.HAVE, counts) == Highlight.NONE


def test_highlight_owned_never_highlights():
    counts = FriendStatusCounts(have=["A"], want=["B"], unowned=["C"])
    assert compute_highlight(BlueprintStatus.OWNED, counts) == Highlight.NONE


# ---- reconcile_active_friends -----------------------------------------------------


def test_reconcile_new_friend_defaults_active():
    result = reconcile_active_friends(
        new_friend_ids=["A", "B"], previous_friend_ids=["A"], previous_active_ids=["A"]
    )
    assert set(result) == {"A", "B"}


def test_reconcile_preserves_previously_inactive_friend():
    result = reconcile_active_friends(
        new_friend_ids=["A", "B"], previous_friend_ids=["A", "B"], previous_active_ids=["A"]
    )
    assert set(result) == {"A"}


def test_reconcile_drops_removed_friend():
    result = reconcile_active_friends(
        new_friend_ids=["A"], previous_friend_ids=["A", "B"], previous_active_ids=["A", "B"]
    )
    assert set(result) == {"A"}


def test_reconcile_empty_roster():
    assert reconcile_active_friends([], ["A"], ["A"]) == []


# ---- visible_friend_ids ----------------------------------------------------------


def test_visible_friend_ids_drops_unresolved_entries():
    cache = {"A": FriendProfileSnapshot(arbg_user_id="A")}
    assert visible_friend_ids(["A", "B"], cache) == ["A"]


def test_visible_friend_ids_preserves_order():
    cache = {
        "A": FriendProfileSnapshot(arbg_user_id="A"),
        "B": FriendProfileSnapshot(arbg_user_id="B"),
    }
    assert visible_friend_ids(["B", "A"], cache) == ["B", "A"]


def test_visible_friend_ids_empty_cache():
    cache: dict = {}
    assert visible_friend_ids(["A", "B"], cache) == []


# ---- discoverable_steam_friends ----------------------------------------------------


def test_discoverable_steam_friends_returns_matches():
    matched = [{"arbg_user_id": "GBLN-A", "steam_id": "111"}, {"arbg_user_id": "GBLN-B", "steam_id": "222"}]
    result = discoverable_steam_friends(["111", "222"], matched, already_added_ids=[])
    assert [c["arbg_user_id"] for c in result] == ["GBLN-A", "GBLN-B"]


def test_discoverable_steam_friends_excludes_already_added():
    matched = [{"arbg_user_id": "GBLN-A", "steam_id": "111"}, {"arbg_user_id": "GBLN-B", "steam_id": "222"}]
    result = discoverable_steam_friends(["111", "222"], matched, already_added_ids=["GBLN-A"])
    assert [c["arbg_user_id"] for c in result] == ["GBLN-B"]


def test_discoverable_steam_friends_orders_by_steam_friend_list_order():
    matched = [{"arbg_user_id": "GBLN-A", "steam_id": "111"}, {"arbg_user_id": "GBLN-B", "steam_id": "222"}]
    result = discoverable_steam_friends(["222", "111"], matched, already_added_ids=[])
    assert [c["arbg_user_id"] for c in result] == ["GBLN-B", "GBLN-A"]


def test_discoverable_steam_friends_ignores_unmatched_steam_ids():
    matched = [{"arbg_user_id": "GBLN-A", "steam_id": "111"}]
    result = discoverable_steam_friends(["111", "999"], matched, already_added_ids=[])
    assert [c["arbg_user_id"] for c in result] == ["GBLN-A"]


def test_discoverable_steam_friends_empty_inputs():
    assert discoverable_steam_friends([], [], []) == []
