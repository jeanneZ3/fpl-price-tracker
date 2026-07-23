# FPL Price Tracker

Personal Fantasy Premier League price tracker: fetch player data from the
FPL API, store one snapshot per gameweek in SQLite, and explore price,
points, and availability trends in a Streamlit dashboard.

Live dashboard: https://fpl-price-tracker.streamlit.app/

## Project layout

```
app/app.py                     Streamlit dashboard entry point
src/api/fpl_api.py             FPL bootstrap-static fetch + lookups
src/database/database_setup.py SQLite schema (players, player_snapshots)
src/database/database_queries.py  Upsert / read queries
src/dashboard/chart_helpers.py Pure helpers for chart color/shape encoding and KPIs
src/update/update_prices.py    Script that pulls one gameweek snapshot
data/fpl.db                    SQLite database (committed to the repo)
tests/                         pytest suite
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # includes runtime + test deps
```

## Pulling a snapshot

```bash
.venv/bin/python -m src.update.update_prices [--gameweek N]
```

Gameweek defaults to auto-detection from the FPL API (0 for the preseason
baseline). Run this once before the season starts, then again after each
gameweek's price changes have settled, and commit `data/fpl.db`.

## Running the dashboard locally

```bash
.venv/bin/streamlit run app/app.py
```

Filters (position, team, player) live in the sidebar. Two tabs:

- **Compare Players** — price-over-gameweeks and points-per-gameweek
  charts for the selected players, plus their current availability status.
  Chart **color always encodes team** and point **shape always encodes
  position** (circle=GKP, square=DEF, triangle=MID, diamond=FWD) — not one
  arbitrary hue per player — so the legend stays meaningful once more than
  a couple of players are selected. Each player is labeled directly on
  their line; click a legend entry to highlight just that team.
- **All Players** — full sortable/searchable table of latest price,
  points, ownership, and status.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Tests cover the pure logic in `src/dashboard/chart_helpers.py` (team
color/position shape mapping, KPI and price-mover calculations, and label
de-collision for the price chart).

## Deployment

Hosted on Streamlit Community Cloud, pointed at `app/app.py` on the `main`
branch. Every push to `main` auto-redeploys — pull a new snapshot, commit
`data/fpl.db`, and push to update the live site.

## Data captured per snapshot

| Field | Why it matters |
|---|---|
| `price` | The core metric being tracked |
| `total_points` / `event_points` | Performance context next to price |
| `minutes` | Explains points (or lack of) |
| `status` / `news` / `chance_of_playing_this_round` | Availability at a glance |
| `selected_by_percent` | Ownership often correlates with price moves |
| `form` | Short-term scoring average |
| `position`, `team` | Needed for filtering |

Deliberately left out: ICT index, fixture difficulty, BPS breakdowns,
transfer counts — easy to add later if wanted.

## Open items

- GitHub Actions automation to pull a snapshot near each gameweek's
  price-lock window (deadlines move week to week, so this likely needs to
  read the `events` section of `bootstrap-static` rather than a fixed cron
  schedule).
