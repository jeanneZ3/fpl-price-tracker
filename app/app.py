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
    POSITION_ORDER,
    compute_point_offsets,
)
from src.dashboard.status_helpers import prepare_availability_display
from src.api.squad_import import SquadImportError, fetch_latest_public_squad
from src.database.database_setup import get_connection

CHART_POSITION_COLORS = {
    "GKP": "#000000",  # black
    "DEF": "#A45583",  # mauve
    "MID": "#002FA7",  # Klein Blue
    "FWD": "#FF5500",  # vivid orange
}
CHART_FALLBACK_COLOR = "#7F7F7F"
PLAYER_SELECTION_KEY = "players_to_compare"
POSITION_FILTER_KEY = "position_filter"
TEAM_FILTER_KEY = "team_filter"
PENDING_SQUAD_KEY = "_pending_imported_squad"
IMPORT_NOTICE_KEY = "_squad_import_notice"

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

.position-legend {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem 1rem;
    margin: 0.15rem 0 0.75rem 2.35rem;
    color: #697087;
    font-size: 0.82rem;
}
.position-legend-title {
    flex-basis: 100%;
    margin-bottom: -0.2rem;
}
.position-legend-item {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
}
.position-legend-dot {
    width: 0.72rem;
    height: 0.72rem;
    border-radius: 50%;
    display: inline-block;
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
    return prepare_availability_display(df)


def get_chart_position_color(position: str) -> str:
    """Return the exact chart color without relying on a cached helper module."""
    return CHART_POSITION_COLORS.get(position, CHART_FALLBACK_COLOR)


def render_position_legend() -> None:
    items = "".join(
        (
            '<span class="position-legend-item">'
            f'<span class="position-legend-dot" style="background:{get_chart_position_color(position)}"></span>'
            f"{POSITION_LABELS[position]}</span>"
        )
        for position in POSITION_ORDER
    )
    st.markdown(
        (
            '<div class="position-legend" data-palette-version="app-v2">'
            f'<span class="position-legend-title">Position</span>{items}</div>'
        ),
        unsafe_allow_html=True,
    )


def render_price_and_points_charts(history: pd.DataFrame) -> None:
    history = history.copy()
    duplicate_names = {
        name
        for name, count in history.groupby("web_name")["player_id"].nunique().items()
        if count > 1
    }
    history["chart_name"] = history["web_name"]
    duplicate_mask = history["web_name"].isin(duplicate_names)
    history.loc[duplicate_mask, "chart_name"] = (
        history.loc[duplicate_mask, "web_name"]
        + " ("
        + history.loc[duplicate_mask, "team"]
        + ")"
    )

    last_gw_rows = history[history["gameweek"] == history["gameweek"].max()].copy()
    last_gw_rows["_name_sort"] = last_gw_rows["chart_name"].str.casefold()
    last_gw_rows = last_gw_rows.sort_values(["price", "_name_sort"]).reset_index(drop=True)
    # Keep colliding marks individually readable without making them look as
    # though they belong to different gameweeks. These become literal
    # per-player mark offsets, so Vega-Lite cannot stretch them across the
    # full gameweek band.
    last_gw_rows["x_offset"] = compute_point_offsets(last_gw_rows["price"], spacing=12.0)
    offset_by_player = dict(zip(last_gw_rows["player_id"], last_gw_rows["x_offset"]))

    gameweeks = sorted(history["gameweek"].astype(int).unique().tolist())
    gameweek_domain = [gameweeks[0] - 0.5, gameweeks[-1] + 0.5]
    gameweek_x = alt.X(
        "gameweek:Q",
        title="Gameweek",
        scale=alt.Scale(domain=gameweek_domain, nice=False),
        axis=alt.Axis(values=gameweeks, format="d", labelAngle=0),
    )

    price_layers = []
    for player_id, x_offset in offset_by_player.items():
        player_history = history[history["player_id"] == player_id]
        player_chart = alt.Chart(player_history)
        player_color = get_chart_position_color(player_history["position"].iloc[0])
        price_layers.extend(
            [
                player_chart.mark_line(
                    strokeWidth=2.5,
                    xOffset=float(x_offset),
                    color=player_color,
                ).encode(
                    x=gameweek_x,
                    y=alt.Y(
                        "price:Q",
                        title="Price (£m)",
                        scale=alt.Scale(zero=False, padding=30),
                    ),
                ),
                player_chart.mark_point(
                    filled=True,
                    size=120,
                    strokeWidth=1,
                    stroke="white",
                    xOffset=float(x_offset),
                    color=player_color,
                ).encode(
                    x=gameweek_x,
                    y="price:Q",
                    tooltip=[
                        alt.Tooltip("web_name:N", title="Player"),
                        alt.Tooltip("team:N", title="Team"),
                        alt.Tooltip("position_label:N", title="Position"),
                        alt.Tooltip("gameweek:O", title="Gameweek"),
                        alt.Tooltip("price:Q", title="Price (£m)", format=".1f"),
                        alt.Tooltip("total_points:Q", title="Total points"),
                        alt.Tooltip("event_points:Q", title="GW points"),
                    ],
                ),
            ]
        )

    # A single centered label per price cluster keeps equal-price names on
    # the same horizontal level and prevents nearby markers from covering
    # any part of a name.
    label_rows = (
        last_gw_rows.groupby(["gameweek", "price"], as_index=False)
        .agg(
            player_names=(
                "chart_name",
                lambda names: "  ·  ".join(sorted(names, key=str.casefold)),
            )
        )
    )

    labels = alt.Chart(label_rows).mark_text(
        align="center",
        dy=-16,
        fontSize=11,
        fontWeight="bold",
        color="#303245",
    ).encode(
        x=gameweek_x,
        y=alt.Y("price:Q", title=None, scale=alt.Scale(zero=False, padding=30)),
        text="player_names:N",
    )

    price_chart = (
        alt.layer(*price_layers, labels)
        .properties(height=420)
        .interactive()
    )
    render_position_legend()
    st.altair_chart(price_chart, use_container_width=True)

    bar_layers = []
    for position in POSITION_ORDER:
        position_history = history[history["position"] == position]
        if position_history.empty:
            continue
        bar_layers.append(
            alt.Chart(position_history)
            .mark_bar(
                cornerRadiusTopLeft=3,
                cornerRadiusTopRight=3,
                color=get_chart_position_color(position),
            )
            .encode(
                x=alt.X("gameweek:O", title="Gameweek"),
                y=alt.Y("event_points:Q", title="Points"),
                xOffset="web_name:N",
                tooltip=[
                    alt.Tooltip("web_name:N", title="Player"),
                    alt.Tooltip("team:N", title="Team"),
                    alt.Tooltip("position_label:N", title="Position"),
                    alt.Tooltip("gameweek:O", title="Gameweek"),
                    alt.Tooltip("event_points:Q", title="GW points"),
                ],
            )
        )
    points_chart = alt.layer(*bar_layers).properties(height=320)
    st.subheader("Points Over Gameweeks")
    render_position_legend()
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

# A successful dialog import reruns the full app. Apply its values before any
# sidebar widgets are created so Streamlit can safely reset filters and replace
# the existing player selection.
pending_squad = st.session_state.pop(PENDING_SQUAD_KEY, None)
if pending_squad:
    st.session_state[POSITION_FILTER_KEY] = sorted(df["position"].unique())
    st.session_state[TEAM_FILTER_KEY] = sorted(df["team"].unique())
    st.session_state[PLAYER_SELECTION_KEY] = pending_squad["player_ids"]
    st.session_state[IMPORT_NOTICE_KEY] = pending_squad["message"]

@st.dialog("Import Your Squad")
def show_squad_import_dialog() -> None:
    st.write(
        "Enter your FPL Team ID or paste your team URL. This imports the latest "
        "published 15-player squad and replaces your current player selection."
    )
    entry_reference = st.text_input(
        "FPL Team ID or URL",
        placeholder="e.g. 123456 or fantasy.premierleague.com/entry/123456/event/1",
        key="squad_entry_reference",
    )
    st.caption(
        "No Premier League password is needed. Unpublished transfers cannot be imported."
    )

    if st.button(
        "Import Latest Published Squad",
        type="primary",
        use_container_width=True,
        disabled=not entry_reference.strip(),
    ):
        try:
            with st.spinner("Loading your squad…"):
                squad = fetch_latest_public_squad(entry_reference)
        except SquadImportError as exc:
            st.error(str(exc))
            return

        available_player_ids = set(
            latest["player_id"].drop_duplicates().astype(int).tolist()
        )
        missing_player_ids = [
            player_id
            for player_id in squad.player_ids
            if player_id not in available_player_ids
        ]
        if missing_player_ids:
            st.error(
                "The published squad does not match this dashboard's player data yet. "
                "Please try again after the next data update."
            )
            return

        imported_ids = list(dict.fromkeys(squad.player_ids))
        st.session_state[PENDING_SQUAD_KEY] = {
            "player_ids": imported_ids,
            "message": (
                f"Imported {len(imported_ids)} players from {squad.entry_name} "
                f"(Gameweek {squad.gameweek})."
            ),
        }
        st.rerun()


st.sidebar.header("⚽ Player Selection")
st.sidebar.caption(
    "Import a published FPL squad, or use the filters below to choose players manually."
)

st.sidebar.subheader("Import a Published Squad")
if st.sidebar.button(
    "Import Your Squad",
    type="primary",
    use_container_width=True,
    help="Replace the current selection with your latest publicly available FPL squad.",
):
    show_squad_import_dialog()

st.sidebar.caption(
    "Replaces your current selection. Available after FPL publishes a Gameweek squad."
)

if import_notice := st.session_state.pop(IMPORT_NOTICE_KEY, None):
    st.sidebar.success(import_notice)

st.sidebar.divider()
st.sidebar.subheader("Choose Players Manually")
st.sidebar.caption(
    "First narrow the player list by position or team. Then select individual "
    "players—or select every player matching those filters."
)

positions = st.sidebar.multiselect(
    "Positions",
    sorted(df["position"].unique()),
    default=sorted(df["position"].unique()),
    key=POSITION_FILTER_KEY,
    help="Only players in these positions will appear in the player list.",
)
teams = st.sidebar.multiselect(
    "Teams",
    sorted(df["team"].unique()),
    default=sorted(df["team"].unique()),
    key=TEAM_FILTER_KEY,
    help="Only players from these teams will appear in the player list.",
)

filtered_latest = latest[latest["position"].isin(positions) & latest["team"].isin(teams)]

player_option_rows = filtered_latest[
    ["player_id", "web_name", "team"]
].drop_duplicates(subset=["player_id"])
player_label_by_id = {
    int(row.player_id): f"{row.web_name} ({row.team})"
    for row in player_option_rows.itertuples(index=False)
}
player_options = sorted(
    player_label_by_id,
    key=lambda player_id: player_label_by_id[player_id].casefold(),
)
default_players = player_options[: min(5, len(player_options))]

if PLAYER_SELECTION_KEY not in st.session_state:
    st.session_state[PLAYER_SELECTION_KEY] = default_players
else:
    # Changing the team or position filters can remove widget options. Keep
    # only selections that remain valid before the multiselect is rendered.
    st.session_state[PLAYER_SELECTION_KEY] = [
        player
        for player in st.session_state[PLAYER_SELECTION_KEY]
        if player in player_options
    ]

st.sidebar.caption(f"**{len(player_options)} players** match the current filters.")

select_all_col, clear_col = st.sidebar.columns(2)
if select_all_col.button(
    "Select All",
    disabled=not player_options,
    use_container_width=True,
    help="Select every player matching the current position and team filters.",
):
    st.session_state[PLAYER_SELECTION_KEY] = player_options

if clear_col.button(
    "Clear",
    disabled=not st.session_state[PLAYER_SELECTION_KEY],
    use_container_width=True,
    help="Remove every player from the comparison.",
):
    st.session_state[PLAYER_SELECTION_KEY] = []

selected_player_ids = st.sidebar.multiselect(
    "Players to compare",
    player_options,
    key=PLAYER_SELECTION_KEY,
    format_func=lambda player_id: player_label_by_id.get(player_id, str(player_id)),
    help="Search by player name, then click a result to add it to the comparison.",
)
st.sidebar.caption(f"**{len(selected_player_ids)} selected** for the charts and status table.")

tab_compare, tab_table = st.tabs(["📈 Compare Players", "📋 All Players"])

with tab_compare:
    if not selected_player_ids:
        st.info("Select one or more players in the sidebar to see charts.")
    else:
        history = df[df["player_id"].isin(selected_player_ids)]

        st.subheader("Price Over Gameweeks")
        render_price_and_points_charts(history)

        st.subheader("Current Status")
        status_cols = [
            "web_name",
            "team",
            "position",
            "status_icon",
            "status_label",
            "display_news",
            "display_chance",
        ]
        status_df = (
            latest[latest["player_id"].isin(selected_player_ids)][status_cols]
            .assign(status=lambda d: d["status_icon"] + " " + d["status_label"])
            .drop(columns=["status_icon", "status_label"])
            .rename(
                columns={
                    "web_name": "Player",
                    "team": "Team",
                    "position": "Pos",
                    "display_news": "News",
                    "display_chance": "chance",
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
