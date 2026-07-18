import pytest
import requests

from arc_companion.steam.web_api import (
    SteamFriendsListPrivateError,
    get_friend_list,
    get_player_summaries,
)


class _FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self) -> dict:
        return self._json_data


# ---- get_player_summaries ------------------------------------------------------


def test_get_player_summaries_returns_steamid_to_name_mapping(monkeypatch):
    def fake_get(url, params, timeout):
        assert "GetPlayerSummaries" in url
        assert params["steamids"] == "111,222"
        return _FakeResponse(
            {"response": {"players": [{"steamid": "111", "personaname": "Alice"}, {"steamid": "222", "personaname": "Bob"}]}}
        )

    monkeypatch.setattr(requests, "get", fake_get)
    names = get_player_summaries("fake-key", ["111", "222"])
    assert names == {"111": "Alice", "222": "Bob"}


def test_get_player_summaries_batches_over_100_ids(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["steamids"])
        return _FakeResponse({"response": {"players": []}})

    monkeypatch.setattr(requests, "get", fake_get)
    steam_ids = [str(i) for i in range(150)]
    get_player_summaries("fake-key", steam_ids)
    assert len(calls) == 2
    assert len(calls[0].split(",")) == 100
    assert len(calls[1].split(",")) == 50


def test_get_player_summaries_ignores_malformed_entries(monkeypatch):
    def fake_get(url, params, timeout):
        return _FakeResponse({"response": {"players": [{"steamid": "111"}, {"personaname": "no id"}]}})

    monkeypatch.setattr(requests, "get", fake_get)
    names = get_player_summaries("fake-key", ["111"])
    assert names == {}


def test_get_player_summaries_empty_input_makes_no_call(monkeypatch):
    def fake_get(*a, **kw):
        raise AssertionError("should not be called")

    monkeypatch.setattr(requests, "get", fake_get)
    assert get_player_summaries("fake-key", []) == {}


def test_get_player_summaries_raises_on_http_error(monkeypatch):
    def fake_get(url, params, timeout):
        return _FakeResponse({}, status_code=500)

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        get_player_summaries("fake-key", ["111"])


# ---- get_friend_list -------------------------------------------------------------


def test_get_friend_list_returns_steamids(monkeypatch):
    def fake_get(url, params, timeout):
        assert "GetFriendList" in url
        assert params["relationship"] == "friend"
        return _FakeResponse(
            {"friendslist": {"friends": [{"steamid": "111", "relationship": "friend"}, {"steamid": "222"}]}}
        )

    monkeypatch.setattr(requests, "get", fake_get)
    assert get_friend_list("fake-key", "my-steamid") == ["111", "222"]


def test_get_friend_list_raises_private_error_on_401(monkeypatch):
    def fake_get(url, params, timeout):
        return _FakeResponse({}, status_code=401)

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(SteamFriendsListPrivateError):
        get_friend_list("fake-key", "my-steamid")


def test_get_friend_list_raises_on_other_http_errors(monkeypatch):
    def fake_get(url, params, timeout):
        return _FakeResponse({}, status_code=500)

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        get_friend_list("fake-key", "my-steamid")


def test_get_friend_list_handles_network_failure(monkeypatch):
    def fake_get(*a, **kw):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(requests.ConnectionError):
        get_friend_list("fake-key", "my-steamid")
