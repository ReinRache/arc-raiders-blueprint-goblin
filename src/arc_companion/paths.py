"""Single source of truth for two different kinds of file location this app
needs -- collapses five previously-duplicated `Path(__file__).resolve()
.parents[3]` blocks (data/blueprints.py + four storage/*.py files) into one
place, and makes both frozen-aware (PyInstaller) without changing behavior
for a normal `python main.py` source run.
"""

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Where bundled read-only resources live (data/blueprints.csv,
    data/images/). Frozen: PyInstaller's own bundle-location signal. Not
    frozen: the repo root, same as before this module existed."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _REPO_ROOT


_USER_DATA_FILES = ("config.json", "supabase_session.json", "friends_cache.json")
_APP_DIR_NAME = "ArcRaidersBlueprintGoblin"
# Escape hatch for testing several independent installs side by side (each
# would otherwise share one per-user folder and so one Goblin ID).
_OVERRIDE_ENV = "ARBG_DATA_DIR"


def migrate_legacy_user_data(legacy_dir: Path, new_dir: Path) -> None:
    """One-time upgrade path: earlier builds saved their files next to the
    .exe, so extracting a newer build into a fresh folder started with no
    config at all -- a brand-new Goblin ID and an orphaned cloud row per
    update. Copies (never moves, never overwrites) whichever of the known
    files exist in legacy_dir and are missing from new_dir."""
    new_dir.mkdir(parents=True, exist_ok=True)
    if legacy_dir == new_dir:
        return
    for name in _USER_DATA_FILES:
        source, target = legacy_dir / name, new_dir / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)


@lru_cache(maxsize=1)
def user_data_root() -> Path:
    """Where writable per-install files live (config.json,
    supabase_session.json, friends_cache.json, crash_log.txt).

    Frozen: a per-user folder (%APPDATA%\ArcRaidersBlueprintGoblin) that
    outlives any one extracted copy of the app, so updating is just "extract
    the new zip anywhere" -- progress and identity carry over. Files from
    older builds (next to the .exe) are copied there on first run. Set the
    ARBG_DATA_DIR environment variable to use a different folder.

    Not frozen: the repo root, same as before this module existed."""
    override = os.environ.get(_OVERRIDE_ENV)
    if override:
        root = Path(override)
        root.mkdir(parents=True, exist_ok=True)
        return root
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        root = Path(appdata) / _APP_DIR_NAME
        migrate_legacy_user_data(Path(sys.executable).parent, root)
        return root
    return _REPO_ROOT
