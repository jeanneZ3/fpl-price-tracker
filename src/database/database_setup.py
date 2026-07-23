"""SQLite schema creation."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fpl.db"

CREATE_PLAYERS_TABLE = """
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    web_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL
);
"""

CREATE_PLAYER_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS player_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    gameweek INTEGER NOT NULL,
    date TEXT NOT NULL,
    price REAL NOT NULL,
    total_points INTEGER NOT NULL,
    event_points INTEGER NOT NULL,
    minutes INTEGER NOT NULL,
    status TEXT NOT NULL,
    news TEXT,
    chance_of_playing_this_round INTEGER,
    selected_by_percent REAL,
    form REAL,
    FOREIGN KEY (player_id) REFERENCES players (player_id),
    UNIQUE (player_id, gameweek)
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_PLAYERS_TABLE)
    conn.execute(CREATE_PLAYER_SNAPSHOTS_TABLE)
    conn.commit()
