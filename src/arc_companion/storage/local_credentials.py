import json
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CREDENTIALS_PATH = REPO_ROOT / "credentials.json"


@dataclass
class LocalCredentials:
    # A personal Web API key from steamcommunity.com/dev/apikey — never
    # embedded in the app, never synced to a cloud store. Only relevant if
    # the user links a Steam account (see src/arc_companion/steam/).
    steam_web_api_key: str | None = None


class LocalCredentialsStore:
    def __init__(self, path: Path = DEFAULT_CREDENTIALS_PATH):
        self.path = path

    def load(self) -> LocalCredentials:
        if not self.path.exists():
            return LocalCredentials()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return LocalCredentials(steam_web_api_key=data.get("steam_web_api_key"))

    def save(self, credentials: LocalCredentials) -> None:
        self.path.write_text(json.dumps(asdict(credentials), indent=2), encoding="utf-8")
