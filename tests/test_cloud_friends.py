from types import SimpleNamespace

from arc_companion.cloud.friends import fetch_friend_profiles, fetch_profiles_by_steam_ids


class FakeSelectQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filter_column: str | None = None
        self._ids_filter: set[str] | None = None

    def select(self, columns: str) -> "FakeSelectQuery":
        return self

    def in_(self, column: str, values: list[str]) -> "FakeSelectQuery":
        self._filter_column = column
        self._ids_filter = set(values)
        return self

    def execute(self) -> SimpleNamespace:
        matched = [row for row in self._rows if row.get(self._filter_column) in self._ids_filter]
        return SimpleNamespace(data=matched)


class FakeClient:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.table_calls: list[str] = []

    def table(self, name: str) -> FakeSelectQuery:
        self.table_calls.append(name)
        return FakeSelectQuery(self._rows)


_ROWS = [
    {"arbg_user_id": "GBLN-AAAAA", "steam_id": None, "blueprints_owned": [1], "blueprints_wanted": [], "blueprints_spare": []},
    {"arbg_user_id": "GBLN-BBBBB", "steam_id": None, "blueprints_owned": [], "blueprints_wanted": [2], "blueprints_spare": []},
    {"arbg_user_id": "GBLN-CCCCC", "steam_id": None, "blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": [3]},
]


def test_fetch_friend_profiles_returns_only_requested_rows():
    client = FakeClient(_ROWS)
    result = fetch_friend_profiles(client, ["GBLN-AAAAA", "GBLN-CCCCC"])
    assert {row["arbg_user_id"] for row in result} == {"GBLN-AAAAA", "GBLN-CCCCC"}


def test_fetch_friend_profiles_omits_ids_with_no_matching_row():
    client = FakeClient(_ROWS)
    result = fetch_friend_profiles(client, ["GBLN-AAAAA", "GBLN-NOTFOUND"])
    assert [row["arbg_user_id"] for row in result] == ["GBLN-AAAAA"]


def test_fetch_friend_profiles_empty_list_short_circuits_without_querying():
    client = FakeClient(_ROWS)
    result = fetch_friend_profiles(client, [])
    assert result == []
    assert client.table_calls == []


_STEAM_LINKED_ROWS = [
    {"arbg_user_id": "GBLN-AAAAA", "steam_id": "111", "blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": []},
    {"arbg_user_id": "GBLN-BBBBB", "steam_id": "222", "blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": []},
    {"arbg_user_id": "GBLN-CCCCC", "steam_id": None, "blueprints_owned": [], "blueprints_wanted": [], "blueprints_spare": []},
]


def test_fetch_profiles_by_steam_ids_returns_matching_rows():
    client = FakeClient(_STEAM_LINKED_ROWS)
    result = fetch_profiles_by_steam_ids(client, ["111", "333"])
    assert [row["arbg_user_id"] for row in result] == ["GBLN-AAAAA"]


def test_fetch_profiles_by_steam_ids_empty_list_short_circuits():
    client = FakeClient(_STEAM_LINKED_ROWS)
    result = fetch_profiles_by_steam_ids(client, [])
    assert result == []
    assert client.table_calls == []
