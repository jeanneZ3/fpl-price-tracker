"""Import the latest publicly available squad for an FPL entry."""

from dataclasses import dataclass
import re
from typing import Any

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


def _get_json(url: str, http_client: Any) -> dict:
    try:
        response = http_client.get(url, timeout=15)
        if response.status_code == 404:
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


def fetch_latest_public_squad(
    entry_reference: str, http_client: Any = requests
) -> ImportedSquad:
    """Fetch the latest published picks for an FPL entry.

    This uses public FPL entry data only. It does not request or handle a
    user's Premier League login credentials.
    """
    entry_id = parse_entry_id(entry_reference)
    entry = _get_json(ENTRY_URL.format(entry_id=entry_id), http_client)

    current_event = entry.get("current_event")
    if not isinstance(current_event, int) or current_event < 1:
        raise SquadImportError(
            "This team does not have a publicly available gameweek squad yet."
        )

    picks_payload = _get_json(
        PICKS_URL.format(entry_id=entry_id, gameweek=current_event), http_client
    )
    picks = picks_payload.get("picks")
    if not isinstance(picks, list) or not picks:
        raise SquadImportError(
            "No publicly available players were found for this team."
        )

    try:
        player_ids = tuple(int(pick["element"]) for pick in picks)
    except (KeyError, TypeError, ValueError) as exc:
        raise SquadImportError(
            "Premier League returned squad data in an unexpected format."
        ) from exc

    return ImportedSquad(
        entry_id=entry_id,
        entry_name=str(entry.get("name") or f"Team {entry_id}"),
        player_name=str(entry.get("player_first_name") or "").strip(),
        gameweek=current_event,
        player_ids=player_ids,
    )
