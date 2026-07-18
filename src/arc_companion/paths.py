"""Single source of truth for two different kinds of file location this app
needs -- collapses five previously-duplicated `Path(__file__).resolve()
.parents[3]` blocks (data/blueprints.py + four storage/*.py files) into one
place, and makes both frozen-aware (PyInstaller) without changing behavior
for a normal `python main.py` source run.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Where bundled read-only resources live (data/blueprints.csv,
    data/images/). Frozen: PyInstaller's own bundle-location signal. Not
    frozen: the repo root, same as before this module existed."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _REPO_ROOT


def user_data_root() -> Path:
    """Where writable per-install files live (config.json,
    credentials.json, supabase_session.json, friends_cache.json). Frozen:
    next to the actual .exe -- visible, easy to find/back up/delete, not
    inside PyInstaller's managed _internal/ folder. Not frozen: the repo
    root, same as before this module existed."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return _REPO_ROOT
