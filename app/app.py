"""Streamlit app entry point.

Layout: a hero header, sidebar filters, and two tabs ("Compare Players"
for trend charts, "Player Profile" for the full table). Chart color encodes
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
from src.dashboard.search_helpers import normalize_search_text, player_name_matches
from src.api.squad_import import SquadImportError, fetch_latest_public_squad
from src.database.database_setup import DB_PATH, get_connection

CHART_POSITION_COLORS = {
    "GKP": "#000000",  # black
    "DEF": "#A45583",  # mauve
    "MID": "#002FA7",  # Klein Blue
    "FWD": "#FF5500",  # vivid orange
}
CHART_FALLBACK_COLOR = "#7F7F7F"
PLAYER_SELECTION_KEY = "players_to_compare"
PLAYER_DRAFT_KEY = "players_to_compare_draft"
POSITION_FILTER_KEY = "position_filter"
TEAM_FILTER_KEY = "team_filter"
PENDING_SQUAD_KEY = "_pending_imported_squad"
IMPORT_NOTICE_KEY = "_squad_import_notice"
DEFAULT_TEAM = "Arsenal"

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

.stApp {
    background:
        radial-gradient(circle at 82% 8%, rgba(164, 85, 131, 0.10), transparent 28rem),
        linear-gradient(180deg, #f8f6fa 0%, #f3f0f6 100%);
    color: #292333;
}

[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1480px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.fpl-hero {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 88% 20%, rgba(255, 85, 0, 0.28), transparent 14rem),
        linear-gradient(120deg, #26002a 0%, #531458 55%, #7d315f 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 22px;
    padding: 2.1rem 2.35rem;
    margin-bottom: 1rem;
    box-shadow: 0 18px 42px rgba(55, 0, 60, 0.22);
}
.fpl-hero::after {
    content: "";
    position: absolute;
    width: 15rem;
    height: 15rem;
    right: -5rem;
    bottom: -8rem;
    border: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: 50%;
    box-shadow:
        0 0 0 2.2rem rgba(255, 255, 255, 0.035),
        0 0 0 4.4rem rgba(255, 255, 255, 0.025);
}
.fpl-hero h1 {
    color: #ffffff;
    font-weight: 800;
    font-size: 2.15rem;
    letter-spacing: -0.035em;
    margin: 0 0 0.45rem 0;
}
.fpl-hero p {
    color: rgba(255, 255, 255, 0.82);
    font-size: 0.95rem;
    margin: 0;
}
.fpl-hero .fpl-data-note {
    color: rgba(255, 255, 255, 0.64);
    font-size: 0.82rem;
    margin-top: 0.45rem;
}

h3 {
    border-left: 4px solid #a45583;
    padding-left: 0.7rem;
    margin-top: 1.6rem !important;
    color: #302638;
    letter-spacing: -0.02em;
}

section[data-testid="stSidebar"] {
    background:
        radial-gradient(circle at 30% 0%, rgba(164, 85, 131, 0.35), transparent 17rem),
        linear-gradient(180deg, #2c1230 0%, #1d1023 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding-top: 0.25rem;
}

section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    margin-top: -2rem;
}

section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
    gap: 0.5rem;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] label {
    color: #ffffff !important;
}

section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #cfc3d5;
    line-height: 1.45;
}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong {
    color: rgba(255, 255, 255, 0.92);
}

section[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.13);
}

section[data-testid="stSidebar"] .stMultiSelect label,
section[data-testid="stSidebar"] .stTextInput label {
    font-weight: 600;
}

section[data-testid="stSidebar"] h3 {
    border-left: none;
    padding-left: 0;
    margin-top: 0.45rem !important;
    font-size: 1rem;
}

section[data-testid="stSidebar"] [data-testid="stDivider"] {
    margin: 0.15rem 0;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: rgba(255, 255, 255, 0.96);
    border-color: rgba(255, 255, 255, 0.12);
    border-radius: 10px;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div:first-child {
    max-height: 7rem;
    overflow-y: auto;
    align-content: flex-start;
}

/* Give the clear-all and menu controls distinct, accessible tap targets. */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div:last-child {
    gap: 0.45rem;
    padding: 0.25rem 0.45rem;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div:last-child > svg {
    box-sizing: content-box;
    width: 1.25rem !important;
    height: 1.25rem !important;
    padding: 0.75rem;
    background: rgba(55, 0, 60, 0.055);
    border-radius: 12px;
    cursor: pointer;
    transition: background 120ms ease, color 120ms ease;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div:last-child > svg:hover {
    background: rgba(55, 0, 60, 0.09);
    color: #37003c;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div:last-child > svg:focus-visible {
    outline: 2px solid #a45583;
    outline-offset: 1px;
}

section[data-testid="stSidebar"] .stButton > button {
    min-height: 2.45rem;
    border-radius: 10px;
    font-weight: 700;
    transition: transform 120ms ease, box-shadow 120ms ease;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.18);
}

section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #ff6b24, #ff5500);
    border-color: #ff6b24;
    color: #ffffff;
}

section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:disabled {
    background: rgba(255, 255, 255, 0.18) !important;
    border-color: rgba(255, 255, 255, 0.28) !important;
    color: rgba(255, 255, 255, 0.82) !important;
    opacity: 1 !important;
}

section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:disabled p {
    color: rgba(255, 255, 255, 0.82) !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {
    color: rgba(255, 255, 255, 0.88) !important;
    font-weight: 700;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
    color: rgba(255, 255, 255, 0.72) !important;
}

section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: rgba(255, 255, 255, 0.09);
    border-color: rgba(255, 255, 255, 0.20);
    color: #ffffff;
}

.stTabs [data-baseweb="tab-list"] {
    width: fit-content;
    gap: 0.65rem;
    background: transparent;
    border: none;
    padding: 0.3rem 0;
    box-shadow: none;
}

.stTabs button[data-baseweb="tab"] {
    height: 3.2rem;
    border: 1px solid transparent;
    border-bottom: none !important;
    border-radius: 16px !important;
    padding: 0.65rem 1.8rem !important;
    margin: 0.2rem 0 !important;
    color: #655b6c;
    font-weight: 700;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;
}

.stTabs button[data-baseweb="tab"][aria-selected="true"] {
    background: rgba(164, 85, 131, 0.13) !important;
    border-color: rgba(164, 85, 131, 0.24) !important;
    color: #61334f !important;
    box-shadow: 0 5px 14px rgba(97, 51, 79, 0.07);
}

.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
    height: 0 !important;
    background: transparent !important;
}

[data-testid="stVegaLiteChart"],
[data-testid="stDataFrame"] {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #e5dce8;
    border-radius: 18px;
    padding: 0.85rem;
    box-shadow: 0 10px 28px rgba(47, 29, 55, 0.065);
    overflow: hidden;
}

[data-testid="stTextInput"] input {
    border-radius: 10px;
}

[data-testid="stAlert"] {
    border-radius: 14px;
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

@media (max-width: 760px) {
    .block-container {
        padding-top: 1rem;
    }
    .fpl-hero {
        padding: 1.55rem 1.4rem;
        border-radius: 18px;
    }
    .fpl-hero h1 {
        font-size: 1.75rem;
    }
}
</style>
"""


@st.cache_data(ttl=600)
def load_data(database_mtime_ns: int) -> pd.DataFrame:
    """Load snapshots, invalidating the cache when the database changes."""
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


def apply_chart_theme(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """Apply the dashboard's shared typography and subtle chart furniture."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            domainColor="#D8D0DD",
            gridColor="#EEE9F1",
            labelColor="#6E6475",
            labelFont="Inter",
            labelFontSize=11,
            tickColor="#D8D0DD",
            titleColor="#4A3F51",
            titleFont="Inter",
            titleFontSize=12,
            titleFontWeight=600,
            titlePadding=14,
        )
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
    price_chart = apply_chart_theme(price_chart)
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
    points_chart = apply_chart_theme(
        alt.layer(*bar_layers).properties(height=320)
    )
    st.subheader("Points Over Gameweeks")
    render_position_legend()
    st.altair_chart(points_chart, use_container_width=True)


st.set_page_config(page_title="FPL Price Tracker", page_icon="⚽", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

df = load_data(DB_PATH.stat().st_mtime_ns)

if df.empty:
    st.markdown(
        '<div class="fpl-hero"><h1>⚽ FPL Price Tracker</h1>'
        "<p>No data yet.</p></div>",
        unsafe_allow_html=True,
    )
    st.warning("No data yet. Run `python -m src.update.update_prices` to pull a snapshot.")
    st.stop()

latest_gw = df["gameweek"].max()
latest = df[df["gameweek"] == df.groupby("player_id")["gameweek"].transform("max")]
st.markdown(
    f"""
    <div class="fpl-hero">
        <h1>⚽ FPL Price Tracker</h1>
        <p>Compare FPL player prices, gameweek points, ownership, form, and
        availability. You can import your own squad or select players manually
        in the sidebar.</p>
        <p class="fpl-data-note">Data through gameweek {latest_gw}
        · Updated {df['date'].max()}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# A successful dialog import reruns the full app. Apply its values before any
# sidebar widgets are created so Streamlit can safely reset filters and replace
# the existing player selection.
pending_squad = st.session_state.pop(PENDING_SQUAD_KEY, None)
if pending_squad:
    st.session_state[POSITION_FILTER_KEY] = []
    st.session_state[TEAM_FILTER_KEY] = []
    st.session_state[PLAYER_SELECTION_KEY] = pending_squad["player_ids"]
    st.session_state[PLAYER_DRAFT_KEY] = pending_squad["player_ids"]
    st.session_state[IMPORT_NOTICE_KEY] = pending_squad["message"]

@st.dialog("Import Your Squad")
def show_squad_import_dialog() -> None:
    st.write(
        "Enter your FPL Team ID or paste your team URL. This imports the latest "
        "published 15-player squad and replaces your current player selection."
    )
    st.markdown(
        "**How to find your Team ID**\n\n"
        "1. Log in to [Fantasy Premier League](https://fantasy.premierleague.com/) "
        "and open **Points** or **Gameweek History**.\n"
        "2. Find `/entry/1234567/` in the page URL. The number—`1234567` in this "
        "example—is your Team ID.\n"
        "3. Paste the number or the entire FPL team URL below."
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


st.sidebar.header("⚽ Choose Players")
st.sidebar.caption(
    "Build your comparison using either option below."
)
st.sidebar.markdown("**Option 1: Import your own squad**")

if st.sidebar.button(
    "Import Your Squad",
    type="primary",
    use_container_width=True,
    help="Replace the current selection with your latest publicly available FPL squad.",
):
    show_squad_import_dialog()

if import_notice := st.session_state.pop(IMPORT_NOTICE_KEY, None):
    st.sidebar.success(import_notice)

st.sidebar.divider()
manual_picker = st.sidebar.expander(
    "Option 2: Select players manually",
    expanded=False,
)
manual_picker.caption(
    "Filter the list, choose players, then update the dashboard."
)

positions = manual_picker.multiselect(
    "Positions",
    sorted(df["position"].unique()),
    default=[],
    key=POSITION_FILTER_KEY,
    placeholder="All positions",
    help="Leave empty to include every position.",
)
teams = manual_picker.multiselect(
    "Teams",
    sorted(df["team"].unique()),
    default=[],
    key=TEAM_FILTER_KEY,
    placeholder="All teams",
    help="Leave empty to include every team.",
)

position_matches = (
    latest["position"].isin(positions)
    if positions
    else pd.Series(True, index=latest.index)
)
team_matches = (
    latest["team"].isin(teams)
    if teams
    else pd.Series(True, index=latest.index)
)
filtered_latest = latest[position_matches & team_matches]

player_option_rows = filtered_latest[
    ["player_id", "web_name", "team"]
].drop_duplicates(subset=["player_id"])
player_name_by_id = {
    int(row.player_id): row.web_name
    for row in player_option_rows.itertuples(index=False)
}
player_team_by_id = {
    int(row.player_id): row.team
    for row in player_option_rows.itertuples(index=False)
}
player_label_by_id = {
    int(row.player_id): f"{row.web_name} ({row.team})"
    for row in player_option_rows.itertuples(index=False)
}
player_options = sorted(
    player_label_by_id,
    key=lambda player_id: player_label_by_id[player_id].casefold(),
)
default_players = [
    player_id
    for player_id in player_options
    if player_team_by_id[player_id] == DEFAULT_TEAM
]
if not default_players:
    default_players = player_options[: min(5, len(player_options))]

if PLAYER_SELECTION_KEY not in st.session_state:
    st.session_state[PLAYER_SELECTION_KEY] = default_players

if PLAYER_DRAFT_KEY not in st.session_state:
    st.session_state[PLAYER_DRAFT_KEY] = list(
        st.session_state[PLAYER_SELECTION_KEY]
    )
else:
    # Filters only change the draft shown in the picker. The charts retain the
    # last applied selection until the user explicitly applies the new draft.
    st.session_state[PLAYER_DRAFT_KEY] = [
        player
        for player in st.session_state[PLAYER_DRAFT_KEY]
        if player in player_options
    ]

manual_picker.caption(f"**{len(player_options)} players** match the current filters.")

select_all_col, clear_col = manual_picker.columns(2)
if select_all_col.button(
    "Select Matching",
    disabled=not player_options,
    use_container_width=True,
    help="Select every player matching the current position and team filters.",
):
    st.session_state[PLAYER_DRAFT_KEY] = player_options

if clear_col.button(
    "Clear Players",
    disabled=not st.session_state[PLAYER_DRAFT_KEY],
    use_container_width=True,
    help="Remove every player from the draft selection.",
):
    st.session_state[PLAYER_DRAFT_KEY] = []

draft_ids_for_display = set(st.session_state[PLAYER_DRAFT_KEY])

def format_player_option(player_id: int) -> str:
    """Show a searchable alias in choices, but never in selected-player chips."""
    label = player_label_by_id.get(player_id, str(player_id))
    if player_id in draft_ids_for_display:
        return label

    player_name = player_name_by_id.get(player_id, "")
    normalized_name = normalize_search_text(player_name)
    if normalized_name != player_name.casefold():
        search_alias = normalized_name.title()
        return f"{label} · Search: {search_alias}"
    return label

draft_player_ids = manual_picker.multiselect(
    "Players to compare",
    player_options,
    key=PLAYER_DRAFT_KEY,
    format_func=format_player_option,
    placeholder="Type a player name",
    help="Search without accents if needed—for example, Odegaard finds Ødegaard.",
)

selection_has_changes = list(draft_player_ids) != list(
    st.session_state[PLAYER_SELECTION_KEY]
)
apply_button_label = "Update Dashboard" if selection_has_changes else "✓ Dashboard Updated"
if manual_picker.button(
    apply_button_label,
    type="primary",
    disabled=not selection_has_changes,
    use_container_width=True,
    help="Refresh the charts and status table with this player selection.",
):
    st.session_state[PLAYER_SELECTION_KEY] = list(draft_player_ids)
    st.rerun()

if selection_has_changes:
    manual_picker.caption(
        f"**{len(draft_player_ids)} selected** · Click Update Dashboard to apply."
    )
else:
    manual_picker.caption(
        f"**{len(draft_player_ids)} selected** in the charts and status table."
    )

selected_player_ids = st.session_state[PLAYER_SELECTION_KEY]

tab_compare, tab_table = st.tabs(["📈 Compare Players", "👤 Player Profile"])

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
        table_df = table_df[
            table_df["web_name"].map(
                lambda player_name: player_name_matches(player_name, search)
            )
        ]

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
