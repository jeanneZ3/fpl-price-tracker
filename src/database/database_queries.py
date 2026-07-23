"""SQLite read/write queries."""

import sqlite3

UPSERT_PLAYER = """
INSERT INTO players (player_id, web_name, team, position)
VALUES (:player_id, :web_name, :team, :position)
ON CONFLICT (player_id) DO UPDATE SET
    web_name = excluded.web_name,
    team = excluded.team,
    position = excluded.position;
"""

UPSERT_SNAPSHOT = """
INSERT INTO player_snapshots (
    player_id, gameweek, date, price, total_points, event_points,
    minutes, status, news, chance_of_playing_this_round,
    selected_by_percent, form
)
VALUES (
    :player_id, :gameweek, :date, :price, :total_points, :event_points,
    :minutes, :status, :news, :chance_of_playing_this_round,
    :selected_by_percent, :form
)
ON CONFLICT (player_id, gameweek) DO UPDATE SET
    date = excluded.date,
    price = excluded.price,
    total_points = excluded.total_points,
    event_points = excluded.event_points,
    minutes = excluded.minutes,
    status = excluded.status,
    news = excluded.news,
    chance_of_playing_this_round = excluded.chance_of_playing_this_round,
    selected_by_percent = excluded.selected_by_percent,
    form = excluded.form;
"""


def upsert_players(conn: sqlite3.Connection, players: list[dict]) -> None:
    conn.executemany(UPSERT_PLAYER, players)
    conn.commit()


def upsert_snapshots(conn: sqlite3.Connection, snapshots: list[dict]) -> None:
    conn.executemany(UPSERT_SNAPSHOT, snapshots)
    conn.commit()


def get_latest_snapshots(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Latest snapshot row per player, joined with player info."""
    conn.row_factory = sqlite3.Row
    query = """
        SELECT p.web_name, p.team, p.position, s.*
        FROM player_snapshots s
        JOIN players p ON p.player_id = s.player_id
        WHERE s.gameweek = (
            SELECT MAX(gameweek) FROM player_snapshots WHERE player_id = s.player_id
        )
    """
    return conn.execute(query).fetchall()


def get_price_history(conn: sqlite3.Connection, player_id: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    query = """
        SELECT gameweek, date, price, total_points, event_points
        FROM player_snapshots
        WHERE player_id = ?
        ORDER BY gameweek
    """
    return conn.execute(query, (player_id,)).fetchall()
