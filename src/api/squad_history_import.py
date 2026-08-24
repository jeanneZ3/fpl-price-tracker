"""Import current and historical publicly available squads for an FPL entry."""

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

import requests

ENTRY_URL = "https://fantasy.premierleague.com/api/entry/{entry_id}/"
PICKS_URL = (
    "https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gameweek}/picks/"
)

_ENTRY_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?fantasy\.premierleague\.com/entry/(\d+)(?:/|$)",
    re.IGNORECASE,
)


class SquadImportError(ValueError):
    """A user-facing failure while resolving or loading an FPL squad."""


@dataclass(frozen=True)
class ImportedSquad:
    entry_id: int
    entry_name: str
    player_name: str
    gameweek: int
    player_ids: tuple[int, ...]
    picks_by_gameweek: dict[int, tuple[int, ...]] = field(default_factory=dict)


def parse_entry_id(value: str) -> int:
    """Extract an entry ID from a plain number or official FPL team URL."""
    candidate = value.strip()
    if candidate.isdigit():
        entry_id = int(candidate)
    else:
        match = _ENTRY_URL_PATTERN.search(candidate)
        if not match:
            raise SquadImportError(
                "Enter a numeric FPL Team ID or an official fantasy.premierleague.com "
                "team URL."
            )
        entry_id = int(match.group(1))

    if entry_id <= 0:
        raise SquadImportError("The FPL Team ID must be greater than zero.")
    return entry_id


def _get_json(
    url: str, http_client: Any, *, allow_missing: bool = False
) -> dict | None:
    try:
        response = http_client.get(url, timeout=15)
        if response.status_code == 404:
            if allow_missing:
                return None
            raise SquadImportError(
                "That FPL team could not be found. Check the Team ID or URL."
            )
        response.raise_for_status()
        payload = response.json()
    except SquadImportError:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise SquadImportError(
            "Premier League could not be reached right now. Please try again."
        ) from exc

    if not isinstance(payload, dict):
        raise SquadImportError("Premier League returned an unexpected response.")
    return payload


def _parse_player_ids(payload: dict) -> tuple[int, ...]:
    picks = payload.get("picks")
    if not isinstance(picks, list) or not picks:
        raise SquadImportError(
            "No publicly available players were found for this team."
        )

    try:
        return tuple(int(pick["element"]) for pick in picks)
    except (KeyError, TypeError, ValueError) as exc:
        raise SquadImportError(
            "Premier League returned squad data in an unexpected format."
        ) from exc


def fetch_latest_public_squad(
    entry_reference: str,
    http_client: Any = requests,
    gameweeks: Iterable[int] | None = None,
) -> ImportedSquad:
    """Fetch latest picks plus requested published gameweek squads for an entry.

    This uses public FPL entry data only. It does not request or handle a
    user's Premier League login credentials.
    """
    entry_id = parse_entry_id(entry_reference)
    entry = _get_json(ENTRY_URL.format(entry_id=entry_id), http_client)
    assert entry is not None

    current_event = entry.get("current_event")
    if not isinstance(current_event, int) or current_event < 1:
        raise SquadImportError(
            "This team does not have a publicly available gameweek squad yet."
        )

    picks_payload = _get_json(
        PICKS_URL.format(entry_id=entry_id, gameweek=current_event), http_client
    )
    assert picks_payload is not None
    player_ids = _parse_player_ids(picks_payload)

    requested_gameweeks = {current_event}
    if gameweeks is not None:
        requested_gameweeks.update(
            gameweek
            for gameweek in gameweeks
            if isinstance(gameweek, int) and 1 <= gameweek <= current_event
        )

    picks_by_gameweek = {current_event: player_ids}
    for gameweek in sorted(requested_gameweeks - {current_event}):
        historical_payload = _get_json(
            PICKS_URL.format(entry_id=entry_id, gameweek=gameweek),
            http_client,
            allow_missing=True,
        )
        if historical_payload is not None:
            picks_by_gameweek[gameweek] = _parse_player_ids(historical_payload)

    return ImportedSquad(
        entry_id=entry_id,
        entry_name=str(entry.get("name") or f"Team {entry_id}"),
        player_name=str(entry.get("player_first_name") or "").strip(),
        gameweek=current_event,
        player_ids=player_ids,
        picks_by_gameweek=picks_by_gameweek,
    )
