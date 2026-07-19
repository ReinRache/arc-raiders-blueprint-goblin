from dataclasses import dataclass, field
from enum import Enum, auto

from arc_companion.domain.status import BlueprintStatus, status_for
from arc_companion.storage.friends_cache import FriendProfileSnapshot


@dataclass
class FriendStatusCounts:
    # Each list holds a *display name* (steam_name if resolved, else
    # arbg_user_id -- see friend_status_counts_for) for each active friend in
    # that status for one blueprint -- the list IS the tooltip content,
    # len() is the dot count.
    unowned: list[str] = field(default_factory=list)
    want: list[str] = field(default_factory=list)
    owned: list[str] = field(default_factory=list)
    have: list[str] = field(default_factory=list)

    def for_status(self, status: BlueprintStatus) -> list[str]:
        return {
            BlueprintStatus.UNOWNED: self.unowned,
            BlueprintStatus.WANT: self.want,
            BlueprintStatus.OWNED: self.owned,
            BlueprintStatus.HAVE: self.have,
        }[status]


def friend_status_counts_for(
    blueprint_id: int, active_snapshots: list[FriendProfileSnapshot]
) -> FriendStatusCounts:
    counts = FriendStatusCounts()
    for snapshot in active_snapshots:
        status = status_for(
            blueprint_id,
            set(snapshot.blueprints_owned),
            set(snapshot.blueprints_wanted),
            set(snapshot.blueprints_spare),
        )
        # Prefer the resolved Steam persona name over the bare Goblin ID --
        # only falls back when Steam isn't linked/resolved for that friend,
        # same fallback FriendsSection/MainWindow already use for names.
        display_name = snapshot.steam_name or snapshot.arbg_user_id
        if status == BlueprintStatus.UNOWNED:
            counts.unowned.append(display_name)
        elif status == BlueprintStatus.WANT:
            counts.want.append(display_name)
        elif status == BlueprintStatus.OWNED:
            counts.owned.append(display_name)
        elif status == BlueprintStatus.HAVE:
            counts.have.append(display_name)
    return counts


class Highlight(Enum):
    NONE = auto()
    THIN_GREEN = auto()
    THICK_GREEN = auto()
    THIN_CYAN = auto()
    THICK_CYAN = auto()


def compute_highlight(my_status: BlueprintStatus, counts: FriendStatusCounts) -> Highlight:
    # My own status alone selects the color family (green = "a friend has one
    # I might want", cyan = "I could give mine away") -- the two families are
    # mutually exclusive since a tile has exactly one of my 4 statuses.
    if my_status == BlueprintStatus.WANT:
        return Highlight.THICK_GREEN if counts.have else Highlight.NONE
    if my_status == BlueprintStatus.UNOWNED:
        return Highlight.THIN_GREEN if counts.have else Highlight.NONE
    if my_status == BlueprintStatus.HAVE:
        if counts.want:
            return Highlight.THICK_CYAN
        if counts.unowned:
            return Highlight.THIN_CYAN
        return Highlight.NONE
    return Highlight.NONE  # OWNED never highlights -- a kept copy isn't shareable


def reconcile_active_friends(
    new_friend_ids: list[str], previous_friend_ids: list[str], previous_active_ids: list[str]
) -> list[str]:
    """Previously-active IDs stay active, newly-appeared IDs default to
    active, IDs no longer in the roster are dropped. Needs the *previous*
    roster (not just the previous active set) to tell "existing friend
    toggled off" apart from "brand new friend" -- both look like "not in
    previous_active_ids" otherwise. Operates on the full roster regardless of
    cloud-cache presence, so a friend's on/off preference is already correct
    the moment they first become visible."""
    previously_known = set(previous_friend_ids)
    previously_active = set(previous_active_ids)
    return [
        fid
        for fid in new_friend_ids
        if fid not in previously_known or fid in previously_active
    ]


def visible_friend_ids(friend_ids: list[str], cache: dict[str, FriendProfileSnapshot]) -> list[str]:
    """Order-preserving filter down to friends that actually exist as a row
    in the cache (resolved successfully at least once via
    fetch_friend_profiles). A roster entry that's never been confirmed to
    exist -- hasn't synced yet, a mistyped/invalid Goblin ID, or a future
    Steam-imported friend never given a real Goblin ID -- doesn't show up
    here; Settings remains the place to manage the full roster."""
    return [fid for fid in friend_ids if fid in cache]


def discoverable_steam_friends(
    steam_friend_ids: list[str], matched_profiles: list[dict], already_added_ids: list[str]
) -> list[dict]:
    """Filters fetch_profiles_by_steam_ids's result down to candidates worth
    suggesting: drops any match already in the roster (no point re-suggesting
    someone you've already added), and orders results to match
    steam_friend_ids's order (Steam's own friend-list order) rather than
    arbitrary DB row order. Also naturally dedupes via the steam_id-keyed
    lookup, in case the same profile somehow appears twice."""
    already_added = set(already_added_ids)
    by_steam_id = {p["steam_id"]: p for p in matched_profiles if p.get("steam_id")}
    result = []
    for steam_id in steam_friend_ids:
        profile = by_steam_id.get(steam_id)
        if profile is None or profile.get("arbg_user_id") in already_added:
            continue
        result.append(profile)
    return result
