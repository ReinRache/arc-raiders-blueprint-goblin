from types import SimpleNamespace

from arc_companion.cloud.friends import fetch_friend_profiles


class FakeSelectQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._ids_filter: set[str] | None = None

    def select(self, columns: str) -> "FakeSelectQuery":
        return self

    def in_(self, column: str, values: list[str]) -> "FakeSelectQuery":
        assert column == "arbg_user_id"
        self._ids_filter = set(values)
        return self

    def execute(self) -> SimpleNamespace:
        matched = [row for row in self._rows if row["arbg_user_id"] in self._ids_filter]
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
