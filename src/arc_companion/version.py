"""App version + "is there a newer release?" check.

The version below is the single source of truth: shown in the window title,
Settings, and the crash log, and compared against the latest GitHub Release
tag at startup. Bump it (and tag the GitHub Release `v<version>` to match)
for every public build -- the update check is only as honest as that habit.
"""

from dataclasses import dataclass

import requests

__version__ = "0.1.0"

# "owner/repo" of the public GitHub repository. Set to None to disable the check.
# While None no network call is made at all.
GITHUB_REPO: str | None = "ReinRache/arc-raiders-blueprint-goblin"

_CHECK_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class UpdateInfo:
    version: str  # e.g. "0.2.0", leading "v" stripped
    url: str  # the release's web page -- where the user downloads it


def parse_version(text: str) -> tuple[int, ...] | None:
    """"v1.2.3" / "1.2" -> (1, 2, 3) / (1, 2). None for anything that isn't
    purely dot-separated integers (pre-release suffixes, junk tags) -- an
    unparseable remote tag must never be offered as an "update"."""
    parts = text.strip().lstrip("vV").split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def is_newer(latest: str, current: str) -> bool:
    latest_t, current_t = parse_version(latest), parse_version(current)
    if latest_t is None or current_t is None:
        return False
    # Pad so (1, 2) vs (1, 2, 0) compare equal rather than "older".
    width = max(len(latest_t), len(current_t))
    pad = lambda t: t + (0,) * (width - len(t))  # noqa: E731
    return pad(latest_t) > pad(current_t)


def check_for_update(repo: str | None = None, current: str = __version__) -> UpdateInfo | None:
    """Newest published release if it's newer than `current`, else None.
    Every failure mode (no repo configured, offline, rate-limited, malformed
    response) is also None: an update check must never be able to break or
    even slow app startup -- callers run it off the Tk thread."""
    repo = repo if repo is not None else GITHUB_REPO
    if not repo:
        return None
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=_CHECK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        tag, url = data["tag_name"], data["html_url"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
    if not isinstance(tag, str) or not isinstance(url, str) or not is_newer(tag, current):
        return None
    # The URL is opened in the user's browser on click -- only ever a GitHub
    # page, whatever the response claims.
    if not url.startswith("https://github.com/"):
        return None
    return UpdateInfo(version=tag.strip().lstrip("vV"), url=url)
