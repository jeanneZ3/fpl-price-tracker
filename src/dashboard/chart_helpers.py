"""Pure helper functions for the dashboard's visual encoding and KPIs.

Kept dependency-light (no Streamlit) and side-effect free so they're easy to
unit test. Color/shape choices exist to make the dashboard charts encode
*team* (color) and *position* (shape) instead of one arbitrary hue per
player, so a legend actually carries meaning when several players are
compared at once.
"""

from __future__ import annotations

import hashlib
import colorsys

import pandas as pd

# Primary shirt colour per club. Deliberately real club colors (not an
# arbitrary distinct-hue palette) so the chart reads the way an FPL manager
# already thinks about teams. A handful of clubs share a hue family (several
# reds, several blues) -- that's fine, because color is never the *only*
# signal: shape (position), the legend text, and direct line labels all
# disambiguate too.
TEAM_COLORS: dict[str, str] = {
    "Arsenal": "#EF0107",
    "Aston Villa": "#670E36",
    "Bournemouth": "#DA291C",
    "Brentford": "#E30613",
    "Brighton": "#0057B8",
    "Burnley": "#6C1D45",
    "Chelsea": "#034694",
    "Coventry City": "#78D0F2",
    "Crystal Palace": "#1B458F",
    "Everton": "#003399",
    "Fulham": "#6B7280",
    "Hull City": "#F18A00",
    "Ipswich Town": "#0044A9",
    "Leeds": "#FFCD00",
    "Leicester City": "#003090",
    "Liverpool": "#C8102E",
    "Luton Town": "#F78F1E",
    "Man City": "#6CABDD",
    "Man Utd": "#DA020E",
    "Middlesbrough": "#E01A22",
    "Newcastle": "#1B1B1B",
    "Norwich City": "#FFF200",
    "Nott'm Forest": "#DD0000",
    "Sheffield Utd": "#EE2737",
    "Southampton": "#D71920",
    "Spurs": "#132257",
    "Sunderland": "#EB172F",
    "Watford": "#FBEE23",
    "West Brom": "#122F67",
    "West Ham": "#7A263A",
    "Wolves": "#FDB913",
}

# Formation-inspired shapes: back-line square, midfield triangle, attack
# diamond, keeper circle. Fixed regardless of which 20 clubs are in a given
# season, since positions never change.
POSITION_SHAPES: dict[str, str] = {
    "GKP": "circle",
    "DEF": "square",
    "MID": "triangle-up",
    "FWD": "diamond",
}

POSITION_LABELS: dict[str, str] = {
    "GKP": "Goalkeeper",
    "DEF": "Defender",
    "MID": "Midfielder",
    "FWD": "Forward",
}

POSITION_ORDER: list[str] = ["GKP", "DEF", "MID", "FWD"]

# A vivid FPL-inspired palette with no yellow/green pairing. The hues remain
# distinct on both light and dark backgrounds and are stable across charts.
POSITION_COLORS: dict[str, str] = {
    "GKP": "#6D28D9",
    "DEF": "#2563EB",
    "MID": "#D946EF",
    "FWD": "#F43F5E",
}

_FALLBACK_SHAPE = "circle"
_FALLBACK_COLOR = "#7F7F7F"


def get_team_color(team: str) -> str:
    """Hex color for a team. Unmapped teams (e.g. a newly promoted club)
    get a deterministic color derived from the team name, so the same team
    always renders the same color across app runs without needing a code
    change."""
    if team in TEAM_COLORS:
        return TEAM_COLORS[team]
    digest = hashlib.md5(team.encode("utf-8")).hexdigest()
    hue = int(digest[:8], 16) / 0xFFFFFFFF
    r, g, b = colorsys.hls_to_rgb(hue, 0.42, 0.55)
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


def get_position_shape(position: str) -> str:
    """Altair point-mark shape for a position code. Falls back to a plain
    circle for any unrecognized code rather than raising, since this feeds
    a chart that should degrade gracefully on unexpected data."""
    return POSITION_SHAPES.get(position, _FALLBACK_SHAPE)


def get_position_color(position: str) -> str:
    """Hex color for a position code. Falls back to a neutral grey for any
    unrecognized code rather than raising."""
    return POSITION_COLORS.get(position, _FALLBACK_COLOR)


def build_team_color_scale(teams: list[str]):
    """Altair Scale mapping each team in `teams` to `get_team_color`."""
    import altair as alt

    ordered = sorted(set(teams))
    return alt.Scale(domain=ordered, range=[get_team_color(t) for t in ordered])


def build_position_shape_scale():
    """Altair Scale mapping the four position codes to formation shapes."""
    import altair as alt

    return alt.Scale(domain=POSITION_ORDER, range=[POSITION_SHAPES[p] for p in POSITION_ORDER])


def build_position_color_scale():
    """Altair Scale mapping the four position codes to POSITION_COLORS."""
    import altair as alt

    return alt.Scale(domain=POSITION_ORDER, range=[POSITION_COLORS[p] for p in POSITION_ORDER])


def compute_summary_kpis(df: pd.DataFrame) -> dict:
    """Headline counts for the KPI row: players/teams tracked and the
    latest gameweek covered by the data."""
    if df.empty:
        return {"players_tracked": 0, "teams_tracked": 0, "gameweeks_tracked": 0, "latest_gameweek": None}
    return {
        "players_tracked": int(df["player_id"].nunique()),
        "teams_tracked": int(df["team"].nunique()),
        "gameweeks_tracked": int(df["gameweek"].nunique()),
        "latest_gameweek": int(df["gameweek"].max()),
    }


def compute_price_movers(df: pd.DataFrame) -> dict:
    """Biggest price riser and faller from the first tracked gameweek to
    the latest one, per player. Returns None for both when fewer than two
    gameweeks of history exist yet -- there's nothing to compare, and the
    caller should show a "check back after the next gameweek" state
    instead of a misleading zero-change entry.
    """
    result = {"riser": None, "faller": None}
    if df.empty or df["gameweek"].nunique() < 2:
        return result

    first_gw, last_gw = df["gameweek"].min(), df["gameweek"].max()
    first = df[df["gameweek"] == first_gw].set_index("player_id")["price"]
    last = df[df["gameweek"] == last_gw].set_index("player_id")["price"]
    names = df[df["gameweek"] == last_gw].set_index("player_id")["web_name"]
    teams = df[df["gameweek"] == last_gw].set_index("player_id")["team"]

    common = first.index.intersection(last.index)
    if len(common) == 0:
        return result

    delta = (last.loc[common] - first.loc[common]).sort_values()
    if delta.empty:
        return result

    faller_id, riser_id = delta.index[0], delta.index[-1]

    if delta.loc[faller_id] < 0:
        result["faller"] = {
            "web_name": names.loc[faller_id],
            "team": teams.loc[faller_id],
            "delta": float(delta.loc[faller_id]),
            "price": float(last.loc[faller_id]),
        }
    if delta.loc[riser_id] > 0:
        result["riser"] = {
            "web_name": names.loc[riser_id],
            "team": teams.loc[riser_id],
            "delta": float(delta.loc[riser_id]),
            "price": float(last.loc[riser_id]),
        }
    return result


def compute_label_positions(values: pd.Series, min_gap: float) -> pd.Series:
    """De-collide y-positions for direct chart labels.

    Several players often sit at the exact same price (e.g. a cluster of
    4.5m defenders), which would otherwise stack their name labels on top
    of each other into an unreadable blob. Walking the values in sorted
    order and pushing each one at least `min_gap` above the previous keeps
    every label readable while leaving well-separated values untouched.
    The original index/order is preserved in the result so callers can
    assign it straight back onto a DataFrame column.
    """
    if values.empty or min_gap <= 0:
        return values.copy()

    order = values.sort_values().index
    adjusted: dict = {}
    prev = None
    for idx in order:
        val = values[idx]
        if prev is not None and val - prev < min_gap:
            val = prev + min_gap
        adjusted[idx] = val
        prev = val
    return pd.Series(adjusted).reindex(values.index)


def compute_point_offsets(values: pd.Series, spacing: float) -> pd.Series:
    """Pixel x-offsets that fan out marks sharing the exact same value.

    Several players often land on the exact same price (e.g. a cluster of
    4.5m defenders), which makes their chart points render exactly on top
    of one another. Grouping by value and spreading each group symmetrically
    left/right of center keeps every mark visible without moving points that
    don't collide with anything. The original index/order is preserved so
    callers can assign the result straight back onto a DataFrame column and
    feed it to an Altair xOffset encoding.
    """
    if values.empty:
        return pd.Series(0.0, index=values.index)

    offsets = pd.Series(0.0, index=values.index)
    for _, group in values.groupby(values):
        idx = group.index
        n = len(idx)
        if n <= 1:
            continue
        for i, gi in enumerate(idx):
            offsets[gi] = spacing * (i - (n - 1) / 2)
    return offsets
