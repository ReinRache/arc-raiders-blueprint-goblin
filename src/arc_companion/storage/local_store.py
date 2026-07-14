import json
import time
from pathlib import Path

from arc_companion.storage.base import Store, UserState

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.json"

LOCAL_USER_ID = "local_user"


class LocalJSONStore(Store):
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH):
        self.path = path

    def load_state(self, user_id: str) -> UserState:
        if not self.path.exists():
            return UserState(steam_id=user_id)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("steam_id") != user_id:
            return UserState(steam_id=user_id)
        return UserState(
            steam_id=data["steam_id"],
            blueprints_owned=data.get("blueprints_owned", []),
            blueprints_wanted=data.get("blueprints_wanted", []),
            updated_at=data.get("updated_at", 0),
        )

    def save_state(self, state: UserState) -> None:
        state.updated_at = int(time.time())
        self.path.write_text(
            json.dumps(
                {
                    "steam_id": state.steam_id,
                    "blueprints_owned": state.blueprints_owned,
                    "blueprints_wanted": state.blueprints_wanted,
                    "updated_at": state.updated_at,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
