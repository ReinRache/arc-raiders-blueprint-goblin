import pytest
import requests

from arc_companion import version
from arc_companion.version import UpdateInfo, check_for_update, is_newer, parse_version


@pytest.mark.parametrize(
    "text, expected",
    [("v1.2.3", (1, 2, 3)), ("1.2", (1, 2)), (" V0.10.0 ", (0, 10, 0)), ("1.2.3-beta", None), ("", None), ("latest", None)],
)
def test_parse_version(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize(
    "latest, current, expected",
    [
        ("0.2.0", "0.1.0", True),
        ("v0.10.0", "0.9.0", True),  # numeric, not lexicographic
        ("0.1.0", "0.1.0", False),
        ("0.1", "0.1.0", False),  # padding: equal, not older/newer
        ("0.1.1", "0.1", True),
        ("0.0.9", "0.1.0", False),
        ("garbage", "0.1.0", False),
        ("0.2.0-rc1", "0.1.0", False),  # unparseable tag is never an update
    ],
)
def test_is_newer(latest, current, expected):
    assert is_newer(latest, current) is expected


class FakeResponse:
    def __init__(self, payload=None, status_error=None, json_error=None):
        self._payload, self._status_error, self._json_error = payload, status_error, json_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


def _patch_get(monkeypatch, response=None, raises=None):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if raises:
            raise raises
        return response

    monkeypatch.setattr(version.requests, "get", fake_get)
    return calls


def test_no_repo_configured_makes_no_network_call(monkeypatch):
    calls = _patch_get(monkeypatch, FakeResponse({}))
    monkeypatch.setattr(version, "GITHUB_REPO", None)
    assert check_for_update() is None
    assert calls == []


def test_newer_release_returned(monkeypatch):
    calls = _patch_get(
        monkeypatch, FakeResponse({"tag_name": "v0.2.0", "html_url": "https://github.com/o/r/releases/tag/v0.2.0"})
    )
    assert check_for_update("o/r", current="0.1.0") == UpdateInfo("0.2.0", "https://github.com/o/r/releases/tag/v0.2.0")
    assert calls[0][0] == "https://api.github.com/repos/o/r/releases/latest"
    assert calls[0][1]["timeout"] == 5


def test_same_or_older_release_returns_none(monkeypatch):
    _patch_get(monkeypatch, FakeResponse({"tag_name": "v0.1.0", "html_url": "https://github.com/o/r/x"}))
    assert check_for_update("o/r", current="0.1.0") is None


@pytest.mark.parametrize(
    "response, raises",
    [
        (None, requests.ConnectionError()),
        (FakeResponse(status_error=requests.HTTPError("403")), None),
        (FakeResponse(json_error=ValueError("bad json")), None),
        (FakeResponse({"no_tag": 1}), None),
        (FakeResponse(["not", "a", "dict"]), None),
        (FakeResponse({"tag_name": 5, "html_url": "https://github.com/o/r"}), None),
    ],
)
def test_every_failure_mode_is_none(monkeypatch, response, raises):
    _patch_get(monkeypatch, response, raises)
    assert check_for_update("o/r", current="0.1.0") is None


def test_non_github_url_rejected(monkeypatch):
    _patch_get(monkeypatch, FakeResponse({"tag_name": "v9.0.0", "html_url": "https://evil.example/download"}))
    assert check_for_update("o/r", current="0.1.0") is None
