"""Streamlit app entry point.

Layout: a hero header, sidebar filters, and two tabs ("Compare Players"
for trend charts, "All Players" for the full table). Chart color encodes
*position* -- see src/dashboard/chart_helpers.py -- so a legend stays
meaningful once more than a couple of players are selected, instead of
burning a unique hue per player.
"""

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dashboard.chart_helpers import (
    POSITION_LABELS,
    build_position_color_scale,
    compute_label_positions,
    compute_point_offsets,
)
from src.database.database_setup import get_connection

STATUS_LABELS = {
    "a": "Available",
    "d": "Doubtful",
    "i": "Injured",
    "s": "Suspended",
    "u": "Unavailable",
    "n": "Not available",
}
STATUS_ICONS = {"a": "🟢", "d": "🟡", "i": "🔴", "s": "🔴", "u": "⚪", "n": "⚪"}

ALL_SNAPSHOTS_QUERY = """
    SELECT p.web_name, p.team, p.position, s.*
    FROM player_snapshots s
    JOIN players p ON p.player_id = s.player_id
    ORDER BY s.gameweek
"""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.fpl-hero {
    background: linear-gradient(120deg, #37003c 0%, #6f2da8 55%, #00ff87 130%);
    border-radius: 16px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 8px 24px rgba(55, 0, 60, 0.25);
}
.fpl-hero h1 {
    color: #ffffff;
    font-weight: 800;
    font-size: 2rem;
    margin: 0 0 0.35rem 0;
}
.fpl-hero p {
    color: rgba(255, 255, 255, 0.88);
    font-size: 0.95rem;
    margin: 0;
}

h3 {
    border-left: 4px solid #6f2da8;
    padding-left: 0.6rem;
    margin-top: 1.6rem !important;
}

section[data-testid="stSidebar"] .stMultiSelect label,
section[data-testid="stSidebar"] .stTextInput label {
    font-weight: 600;
}
</style>
"""


@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query(ALL_SNAPSHOTS_QUERY, conn)
    finally:
        conn.close()
    df["status_label"] = df["status"].map(STATUS_LABELS).fillna(df["status"])
    df["status_icon"] = df["status"].map(STATUS_ICONS).fillna("⚪")
    df["position_label"] = df["position"].map(POSITION_LABELS).fillna(df["position"])
    return df


def render_price_and_points_charts(history: pd.DataFrame) -> None:
    position_scale = build_position_color_scale()
    position_legend = alt.Legend(
        title="Position",
        orient="top",
        direction="horizontal",
        columns=4,
        symbolType="circle",
        symbolSize=110,
        labelExpr=(
            "datum.label === 'GKP' ? 'Goalkeeper' : "
            "datum.label === 'DEF' ? 'Defender' : "
            "datum.label === 'MID' ? 'Midfielder' : 'Forward'"
        ),
    )
    legend_select = alt.selection_point(fields=["position"], bind="legend")

    last_gw_rows = history[history["gameweek"] == history["gameweek"].max()].reset_index(drop=True)
    # Keep colliding marks individually readable without making them look as
    # though they belong to different gameweeks. With scale=None, Vega-Lite
    # treats these values as literal pixel offsets rather than stretching the
    # smallest and largest offsets across the full gameweek band.
    last_gw_rows["x_offset"] = compute_point_offsets(last_gw_rows["price"], spacing=12.0)
    offset_by_player = dict(zip(last_gw_rows["web_name"], last_gw_rows["x_offset"]))
    history = history.assign(x_offset=history["web_name"].map(offset_by_player).fillna(0.0))

    base = alt.Chart(history)

    line = base.mark_line(strokeWidth=2.5).encode(
        x=alt.X("gameweek:O", title="Gameweek"),
        y=alt.Y("price:Q", title="Price (£m)", scale=alt.Scale(zero=False)),
        xOffset=alt.XOffset("x_offset:Q", scale=None),
        color=alt.Color(
            "position:N",
            title="Position",
            scale=position_scale,
            legend=position_legend,
        ),
        detail="web_name:N",
        opacity=alt.condition(legend_select, alt.value(1), alt.value(0.25)),
    )
    points = base.mark_point(filled=True, size=120, strokeWidth=1, stroke="white").encode(
        x="gameweek:O",
        y="price:Q",
        xOffset=alt.XOffset("x_offset:Q", scale=None),
        color=alt.Color("position:N", scale=position_scale, legend=None),
        detail="web_name:N",
        opacity=alt.condition(legend_select, alt.value(1), alt.value(0.25)),
        tooltip=[
            alt.Tooltip("web_name:N", title="Player"),
            alt.Tooltip("team:N", title="Team"),
            alt.Tooltip("position_label:N", title="Position"),
            alt.Tooltip("gameweek:O", title="Gameweek"),
            alt.Tooltip("price:Q", title="Price (£m)", format=".1f"),
            alt.Tooltip("total_points:Q", title="Total points"),
            alt.Tooltip("event_points:Q", title="GW points"),
        ],
    ).add_params(legend_select)

    price_span = history["price"].max() - history["price"].min()
    label_gap = max(price_span * 0.05, 0.15)
    last_gw_rows["label_price"] = compute_label_positions(last_gw_rows["price"], label_gap)

    labels = alt.Chart(last_gw_rows).mark_text(
        align="left", dx=10, fontSize=11, fontWeight="bold"
    ).encode(
        x="gameweek:O",
        y=alt.Y("label_price:Q", title=None),
        xOffset=alt.XOffset("x_offset:Q", scale=None),
        text="web_name:N",
        color=alt.Color("position:N", scale=position_scale, legend=None),
    )

    price_chart = (line + points + labels).properties(height=420).interactive()
    st.altair_chart(price_chart, use_container_width=True)

    bar_select = alt.selection_point(fields=["position"], bind="legend")
    points_chart = (
        alt.Chart(history)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("gameweek:O", title="Gameweek"),
            y=alt.Y("event_points:Q", title="Points"),
            xOffset="web_name:N",
            color=alt.Color(
                "position:N",
                title="Position",
                scale=position_scale,
                legend=position_legend,
            ),
            opacity=alt.condition(bar_select, alt.value(1), alt.value(0.3)),
            tooltip=[
                alt.Tooltip("web_name:N", title="Player"),
                alt.Tooltip("team:N", title="Team"),
                alt.Tooltip("position_label:N", title="Position"),
                alt.Tooltip("gameweek:O", title="Gameweek"),
                alt.Tooltip("event_points:Q", title="GW points"),
            ],
        )
        .properties(height=320)
        .add_params(bar_select)
    )
    st.subheader("Points over gameweeks")
    st.altair_chart(points_chart, use_container_width=True)


st.set_page_config(page_title="FPL Price Tracker", page_icon="⚽", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

df = load_data()

if df.empty:
    st.markdown(
        '<div class="fpl-hero"><h1>⚽ FPL Price Tracker</h1>'
        "<p>No data yet.</p></div>",
        unsafe_allow_html=True,
    )
    st.warning("No data yet. Run `python -m src.update.update_prices` to pull a snapshot.")
    st.stop()

latest_gw = df["gameweek"].max()
st.markdown(
    f"""
    <div class="fpl-hero">
        <h1>⚽ FPL Price Tracker</h1>
        <p>Tracking price, points, and availability through gameweek {latest_gw}
        (as of {df['date'].max()}).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

latest = df[df["gameweek"] == df.groupby("player_id")["gameweek"].transform("max")]

st.sidebar.header("⚽ Filters")
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

tab_compare, tab_table = st.tabs(["📈 Compare Players", "📋 All Players"])

with tab_compare:
    if not selected_players:
        st.info("Select one or more players in the sidebar to see charts.")
    else:
        history = df[df["web_name"].isin(selected_players)]

        st.subheader("Price over gameweeks")
        render_price_and_points_charts(history)

        st.subheader("Current status")
        status_cols = [
            "web_name",
            "team",
            "position",
            "status_icon",
            "status_label",
            "news",
            "chance_of_playing_this_round",
        ]
        status_df = (
            latest[latest["web_name"].isin(selected_players)][status_cols]
            .assign(status=lambda d: d["status_icon"] + " " + d["status_label"])
            .drop(columns=["status_icon", "status_label"])
            .rename(
                columns={
                    "web_name": "Player",
                    "team": "Team",
                    "position": "Pos",
                    "news": "News",
                    "chance_of_playing_this_round": "chance",
                }
            )
            .sort_values("Player")
        )
        st.dataframe(
            status_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "status": "Status",
                "chance": st.column_config.ProgressColumn(
                    "Chance of playing", min_value=0, max_value=100, format="%d%%"
                ),
            },
        )

with tab_table:
    search = st.text_input("Search player", placeholder="Type a name…")
    table_df = filtered_latest
    if search:
        table_df = table_df[table_df["web_name"].str.contains(search, case=False, na=False)]

    table_cols = [
        "web_name",
        "team",
        "position",
        "price",
        "total_points",
        "event_points",
        "selected_by_percent",
        "form",
        "status_icon",
        "status_label",
    ]
    display_df = (
        table_df[table_cols]
        .assign(status=lambda d: d["status_icon"] + " " + d["status_label"])
        .drop(columns=["status_icon", "status_label"])
        .rename(
            columns={
                "web_name": "Player",
                "team": "Team",
                "position": "Pos",
                "price": "price_val",
                "total_points": "Total points",
                "event_points": "GW points",
                "selected_by_percent": "ownership",
                "form": "Form",
            }
        )
        .sort_values("price_val", ascending=False)
    )
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "price_val": st.column_config.NumberColumn("Price (£m)", format="£%.1f m"),
            "ownership": st.column_config.ProgressColumn(
                "Selected by", min_value=0, max_value=100, format="%.1f%%"
            ),
            "status": "Status",
        },
    )
    st.caption(f"{len(display_df)} players shown")
