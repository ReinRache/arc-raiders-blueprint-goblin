import json
import time
from pathlib import Path

from arc_companion.identity import generate_arbg_id
from arc_companion.paths import user_data_root
from arc_companion.storage.base import Store, UserState

DEFAULT_CONFIG_PATH = user_data_root() / "config.json"

# Sentinel from before local identity existed — a config.json written by an
# older version of the app has this instead of a real steam_id.
_LEGACY_LOCAL_USER_PLACEHOLDER = "local_user"


class LocalJSONStore(Store):
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH):
        self.path = path

    def load_state(self, user_id: str | None = None) -> UserState:
        if not self.path.exists():
            return UserState(arbg_user_id=generate_arbg_id())
        data = json.loads(self.path.read_text(encoding="utf-8"))

        # Migrate an old-format file (from before arbg_user_id existed):
        # assign a real local identity and null out the old placeholder,
        # rather than discarding the owned/wanted/spare arrays already there.
        arbg_user_id = data.get("arbg_user_id") or generate_arbg_id()
        steam_id = data.get("steam_id")
        if steam_id == _LEGACY_LOCAL_USER_PLACEHOLDER:
            steam_id = None

        return UserState(
            arbg_user_id=arbg_user_id,
            steam_id=steam_id,
            arbg_friend_user_ids=data.get("arbg_friend_user_ids", []),
            arbg_active_friend_ids=data.get("arbg_active_friend_ids", []),
            blueprints_owned=data.get("blueprints_owned", []),
            blueprints_wanted=data.get("blueprints_wanted", []),
            blueprints_spare=data.get("blueprints_spare", []),
            updated_at=data.get("updated_at", 0),
            last_synced_at=data.get("last_synced_at"),
            steam_persona_name=data.get("steam_persona_name"),
        )

    def save_state(self, state: UserState) -> None:
        state.updated_at = int(time.time())
        self.path.write_text(
            json.dumps(
                {
                    "arbg_user_id": state.arbg_user_id,
                    "steam_id": state.steam_id,
                    "arbg_friend_user_ids": state.arbg_friend_user_ids,
                    "arbg_active_friend_ids": state.arbg_active_friend_ids,
                    "blueprints_owned": state.blueprints_owned,
                    "blueprints_wanted": state.blueprints_wanted,
                    "blueprints_spare": state.blueprints_spare,
                    "updated_at": state.updated_at,
                    "last_synced_at": state.last_synced_at,
                    "steam_persona_name": state.steam_persona_name,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
