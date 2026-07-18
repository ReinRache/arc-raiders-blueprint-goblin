import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from arc_companion.paths import user_data_root

DEFAULT_CACHE_PATH = user_data_root() / "friends_cache.json"


@dataclass
class FriendProfileSnapshot:
    # A locally-cached copy of a friend's cloud profiles row -- fetched data,
    # not the designer's own progress, kept separate from UserState/
    # config.json for that reason (see storage/base.py's UserState).
    arbg_user_id: str
    steam_id: str | None = None
    blueprints_owned: list[int] = field(default_factory=list)
    blueprints_wanted: list[int] = field(default_factory=list)
    blueprints_spare: list[int] = field(default_factory=list)
    # Resolved via Steam's GetPlayerSummaries (Stage D), only when the viewer
    # has their own Web API key saved -- None falls back to arbg_user_id for
    # display, same as if Steam were never linked at all.
    steam_name: str | None = None


class FriendsCacheStore:
    def __init__(self, path: Path = DEFAULT_CACHE_PATH):
        self.path = path

    def load(self) -> dict[str, FriendProfileSnapshot]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            arbg_user_id: FriendProfileSnapshot(
                arbg_user_id=arbg_user_id,
                steam_id=entry.get("steam_id"),
                blueprints_owned=entry.get("blueprints_owned", []),
                blueprints_wanted=entry.get("blueprints_wanted", []),
                blueprints_spare=entry.get("blueprints_spare", []),
                steam_name=entry.get("steam_name"),
            )
            for arbg_user_id, entry in data.items()
        }

    def save(self, snapshots: dict[str, FriendProfileSnapshot]) -> None:
        self.path.write_text(
            json.dumps({k: asdict(v) for k, v in snapshots.items()}, indent=2),
            encoding="utf-8",
        )
