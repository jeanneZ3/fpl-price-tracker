import pytest
import requests

from src.api.squad_import import (
    ENTRY_URL,
    PICKS_URL,
    SquadImportError,
    fetch_latest_public_squad,
    parse_entry_id,
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return self.responses[url]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123456", 123456),
        (" https://fantasy.premierleague.com/entry/123456/event/4 ", 123456),
        ("fantasy.premierleague.com/entry/42/history", 42),
    ],
)
def test_parse_entry_id(value, expected):
    assert parse_entry_id(value) == expected


@pytest.mark.parametrize("value", ["", "team 123", "https://example.com/entry/12", "0"])
def test_parse_entry_id_rejects_invalid_values(value):
    with pytest.raises(SquadImportError):
        parse_entry_id(value)


def test_fetch_latest_public_squad():
    entry_id = 123
    gameweek = 6
    client = FakeHttpClient(
        {
            ENTRY_URL.format(entry_id=entry_id): FakeResponse(
                {
                    "name": "My XI",
                    "player_first_name": "Alex",
                    "current_event": gameweek,
                }
            ),
            PICKS_URL.format(entry_id=entry_id, gameweek=gameweek): FakeResponse(
                {"picks": [{"element": player_id} for player_id in range(1, 16)]}
            ),
        }
    )

    squad = fetch_latest_public_squad(str(entry_id), http_client=client)

    assert squad.entry_id == entry_id
    assert squad.entry_name == "My XI"
    assert squad.gameweek == gameweek
    assert squad.player_ids == tuple(range(1, 16))
    assert client.calls == [
        (ENTRY_URL.format(entry_id=entry_id), 15),
        (PICKS_URL.format(entry_id=entry_id, gameweek=gameweek), 15),
    ]


def test_fetch_rejects_entry_without_published_gameweek():
    entry_id = 123
    client = FakeHttpClient(
        {
            ENTRY_URL.format(entry_id=entry_id): FakeResponse(
                {"name": "My XI", "current_event": None}
            )
        }
    )

    with pytest.raises(SquadImportError, match="publicly available gameweek"):
        fetch_latest_public_squad(str(entry_id), http_client=client)


def test_fetch_gives_clear_message_for_unknown_entry():
    entry_id = 999
    client = FakeHttpClient(
        {ENTRY_URL.format(entry_id=entry_id): FakeResponse(status_code=404)}
    )

    with pytest.raises(SquadImportError, match="could not be found"):
        fetch_latest_public_squad(str(entry_id), http_client=client)
