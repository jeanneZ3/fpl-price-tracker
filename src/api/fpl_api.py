"""Functions for fetching data from the FPL API."""

import requests

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def fetch_bootstrap_static() -> dict:
    """Fetch the full bootstrap-static payload (players, teams, positions, events)."""
    response = requests.get(BOOTSTRAP_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def get_team_name_map(bootstrap: dict) -> dict[int, str]:
    """Map team id -> team name."""
    return {team["id"]: team["name"] for team in bootstrap["teams"]}


def get_position_name_map(bootstrap: dict) -> dict[int, str]:
    """Map element_type id -> position name (GKP/DEF/MID/FWD)."""
    return {
        element_type["id"]: element_type["singular_name_short"]
        for element_type in bootstrap["element_types"]
    }


def get_current_gameweek(bootstrap: dict) -> int:
    """Return the id of the current gameweek, or 0 if the season hasn't started yet."""
    for event in bootstrap["events"]:
        if event["is_current"]:
            return event["id"]
    return 0
