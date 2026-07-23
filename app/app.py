"""Streamlit app entry point."""

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.database_setup import get_connection

STATUS_LABELS = {
    "a": "Available",
    "d": "Doubtful",
    "i": "Injured",
    "s": "Suspended",
    "u": "Unavailable",
    "n": "Not available",
}

ALL_SNAPSHOTS_QUERY = """
    SELECT p.web_name, p.team, p.position, s.*
    FROM player_snapshots s
    JOIN players p ON p.player_id = s.player_id
    ORDER BY s.gameweek
"""


@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query(ALL_SNAPSHOTS_QUERY, conn)
    finally:
        conn.close()
    df["status_label"] = df["status"].map(STATUS_LABELS).fillna(df["status"])
    return df


st.set_page_config(page_title="FPL Price Tracker", layout="wide")
st.title("FPL Price Tracker")

df = load_data()

if df.empty:
    st.warning("No data yet. Run `python -m src.update.update_prices` to pull a snapshot.")
    st.stop()

latest_gw = df["gameweek"].max()
latest = df[df["gameweek"] == df.groupby("player_id")["gameweek"].transform("max")]

st.sidebar.header("Filters")
positions = st.sidebar.multiselect(
    "Position", sorted(df["position"].unique()), default=sorted(df["position"].unique())
)
teams = st.sidebar.multiselect(
    "Team", sorted(df["team"].unique()), default=sorted(df["team"].unique())
)

filtered_latest = latest[latest["position"].isin(positions) & latest["team"].isin(teams)]

player_options = sorted(filtered_latest["web_name"].unique())
selected_players = st.sidebar.multiselect(
    "Players to compare",
    player_options,
    default=player_options[: min(5, len(player_options))],
)

st.caption(f"Data through gameweek {latest_gw} ({df['date'].max()})")

if not selected_players:
    st.info("Select one or more players in the sidebar to see charts.")
else:
    history = df[df["web_name"].isin(selected_players)]

    st.subheader("Price over gameweeks")
    price_chart = (
        alt.Chart(history)
        .mark_line(point=True)
        .encode(
            x=alt.X("gameweek:O", title="Gameweek"),
            y=alt.Y("price:Q", title="Price (£m)"),
            color=alt.Color("web_name:N", title="Player"),
            tooltip=["web_name", "gameweek", "price", "total_points", "event_points"],
        )
        .properties(height=350)
    )
    st.altair_chart(price_chart, use_container_width=True)

    st.subheader("Points per gameweek")
    points_chart = (
        alt.Chart(history)
        .mark_bar()
        .encode(
            x=alt.X("gameweek:O", title="Gameweek"),
            y=alt.Y("event_points:Q", title="Points"),
            color=alt.Color("web_name:N", title="Player"),
            xOffset="web_name:N",
            tooltip=["web_name", "gameweek", "event_points"],
        )
        .properties(height=350)
    )
    st.altair_chart(points_chart, use_container_width=True)

    st.subheader("Current status")
    status_cols = [
        "web_name",
        "team",
        "position",
        "status_label",
        "news",
        "chance_of_playing_this_round",
    ]
    st.dataframe(
        latest[latest["web_name"].isin(selected_players)][status_cols]
        .rename(
            columns={
                "web_name": "Player",
                "team": "Team",
                "position": "Pos",
                "status_label": "Status",
                "news": "News",
                "chance_of_playing_this_round": "Chance of playing (%)",
            }
        )
        .sort_values("Player"),
        hide_index=True,
        use_container_width=True,
    )

st.subheader("All players (latest snapshot)")
table_cols = [
    "web_name",
    "team",
    "position",
    "price",
    "total_points",
    "event_points",
    "selected_by_percent",
    "form",
    "status_label",
]
st.dataframe(
    filtered_latest[table_cols]
    .rename(
        columns={
            "web_name": "Player",
            "team": "Team",
            "position": "Pos",
            "price": "Price (£m)",
            "total_points": "Total points",
            "event_points": "GW points",
            "selected_by_percent": "Selected by (%)",
            "form": "Form",
            "status_label": "Status",
        }
    )
    .sort_values("Price (£m)", ascending=False),
    hide_index=True,
    use_container_width=True,
)
