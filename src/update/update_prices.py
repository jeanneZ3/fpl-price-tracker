"""Script for saving gameweek price snapshots."""

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.api.fpl_api import (
    fetch_bootstrap_static,
    get_current_gameweek,
    get_position_name_map,
    get_team_name_map,
)
from src.database.database_setup import create_tables, get_connection
from src.database.database_queries import upsert_players, upsert_snapshots


def build_players_and_snapshots(
    bootstrap: dict, gameweek: int, date: str
) -> tuple[list[dict], list[dict]]:
    team_names = get_team_name_map(bootstrap)
    position_names = get_position_name_map(bootstrap)

    players = []
    snapshots = []
    for element in bootstrap["elements"]:
        players.append(
            {
                "player_id": element["id"],
                "web_name": element["web_name"],
                "team": team_names[element["team"]],
                "position": position_names[element["element_type"]],
            }
        )
        snapshots.append(
            {
                "player_id": element["id"],
                "gameweek": gameweek,
                "date": date,
                "price": element["now_cost"] / 10,
                "total_points": element["total_points"],
                "event_points": element["event_points"],
                "minutes": element["minutes"],
                "status": element["status"],
                "news": element["news"],
                "chance_of_playing_this_round": element["chance_of_playing_this_round"],
                "selected_by_percent": float(element["selected_by_percent"]),
                "form": float(element["form"]),
            }
        )
    return players, snapshots


def run(gameweek: int | None = None) -> int:
    bootstrap = fetch_bootstrap_static()
    if gameweek is None:
        gameweek = get_current_gameweek(bootstrap)
    date = datetime.date.today().isoformat()

    players, snapshots = build_players_and_snapshots(bootstrap, gameweek, date)

    conn = get_connection()
    try:
        create_tables(conn)
        upsert_players(conn, players)
        upsert_snapshots(conn, snapshots)
    finally:
        conn.close()

    print(f"Saved snapshot for gameweek {gameweek}: {len(snapshots)} players ({date}).")
    return gameweek


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save an FPL price/points snapshot.")
    parser.add_argument(
        "--gameweek",
        type=int,
        default=None,
        help="Gameweek to record (0 for preseason baseline). Auto-detected if omitted.",
    )
    args = parser.parse_args()
    run(gameweek=args.gameweek)
