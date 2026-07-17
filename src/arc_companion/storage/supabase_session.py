import json
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SESSION_PATH = REPO_ROOT / "supabase_session.json"


@dataclass
class SupabaseSession:
    # A per-install anonymous-auth session (see cloud/sync.py) — not a
    # user secret like credentials.json, but still per-install and gitignored
    # rather than synced, since it's meaningless on any other machine.
    access_token: str | None = None
    refresh_token: str | None = None


class SupabaseSessionStore:
    def __init__(self, path: Path = DEFAULT_SESSION_PATH):
        self.path = path

    def load(self) -> SupabaseSession:
        if not self.path.exists():
            return SupabaseSession()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return SupabaseSession(
            access_token=data.get("access_token"), refresh_token=data.get("refresh_token")
        )

    def save(self, session: SupabaseSession) -> None:
        self.path.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
