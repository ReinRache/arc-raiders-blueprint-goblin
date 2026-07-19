import pytest
from supabase_functions.errors import FunctionsHttpError

from arc_companion.cloud.steam_proxy import (
    SteamFriendsListPrivateError,
    SteamProxyRateLimitedError,
    get_friend_list,
    get_player_summaries,
)


class FakeFunctions:
    def __init__(self, response=None, error: FunctionsHttpError | None = None):
        self._response = response
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    def invoke(self, function_name: str, invoke_options: dict | None = None):
        self.calls.append((function_name, invoke_options))
        if self._error is not None:
            raise self._error
        return self._response


class FakeClient:
    def __init__(self, response=None, error: FunctionsHttpError | None = None):
        self.functions = FakeFunctions(response, error)


# ---- get_player_summaries ---------------------------------------------------


def test_get_player_summaries_returns_steamid_to_name_mapping():
    client = FakeClient(response={"111": "Alice", "222": "Bob"})
    names = get_player_summaries(client, ["111", "222"])
    assert names == {"111": "Alice", "222": "Bob"}
    function_name, options = client.functions.calls[0]
    assert function_name == "steam-player-summaries"
    assert options == {"body": {"steam_ids": ["111", "222"]}, "responseType": "json"}


def test_get_player_summaries_empty_input_makes_no_call():
    client = FakeClient(response={"should": "not be returned"})
    assert get_player_summaries(client, []) == {}
    assert client.functions.calls == []


def test_get_player_summaries_rate_limited_raises_specific_error():
    client = FakeClient(error=FunctionsHttpError("rate_limited", 429))
    with pytest.raises(SteamProxyRateLimitedError):
        get_player_summaries(client, ["111"])


def test_get_player_summaries_other_http_error_propagates_unchanged():
    client = FakeClient(error=FunctionsHttpError("boom", 500))
    with pytest.raises(FunctionsHttpError):
        get_player_summaries(client, ["111"])


# ---- get_friend_list ---------------------------------------------------------


def test_get_friend_list_returns_steamids():
    client = FakeClient(response={"steam_ids": ["111", "222"]})
    assert get_friend_list(client, "my-steamid") == ["111", "222"]
    function_name, options = client.functions.calls[0]
    assert function_name == "steam-friend-list"
    assert options == {"body": {"steam_id": "my-steamid"}, "responseType": "json"}


def test_get_friend_list_raises_private_error_on_friends_list_private():
    client = FakeClient(error=FunctionsHttpError("friends_list_private", 403))
    with pytest.raises(SteamFriendsListPrivateError):
        get_friend_list(client, "my-steamid")


def test_get_friend_list_rate_limited_raises_specific_error():
    client = FakeClient(error=FunctionsHttpError("rate_limited", 429))
    with pytest.raises(SteamProxyRateLimitedError):
        get_friend_list(client, "my-steamid")


def test_get_friend_list_unrelated_403_is_not_mistaken_for_private_list():
    client = FakeClient(error=FunctionsHttpError("something_else", 403))
    with pytest.raises(FunctionsHttpError):
        get_friend_list(client, "my-steamid")


def test_get_friend_list_other_http_error_propagates_unchanged():
    client = FakeClient(error=FunctionsHttpError("boom", 500))
    with pytest.raises(FunctionsHttpError):
        get_friend_list(client, "my-steamid")
