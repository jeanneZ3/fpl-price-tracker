"""Helpers for presenting FPL availability data consistently."""

from __future__ import annotations

import pandas as pd


NEWS_CHANCE_PATTERN = r"\s*[-–—]\s*(\d{1,3})%\s+chance of playing\s*$"

STATUS_CHANCE_DEFAULTS = {
    "a": 100,
    "i": 0,
    "s": 0,
    "u": 0,
    "n": 0,
}


def prepare_availability_display(df: pd.DataFrame) -> pd.DataFrame:
    """Separate descriptive news from the numeric chance of playing.

    The FPL feed sometimes embeds a percentage in ``news`` while leaving
    ``chance_of_playing_this_round`` empty. Prefer the structured API value,
    then fall back to a percentage parsed from news, and finally use definitive
    status defaults for available or unavailable players.
    """
    result = df.copy()
    news = result["news"].fillna("").astype(str)

    api_chance = pd.to_numeric(
        result["chance_of_playing_this_round"], errors="coerce"
    )
    news_chance = pd.to_numeric(
        news.str.extract(NEWS_CHANCE_PATTERN, expand=False), errors="coerce"
    )
    status_default = result["status"].map(STATUS_CHANCE_DEFAULTS)

    result["display_chance"] = (
        api_chance.fillna(news_chance)
        .fillna(status_default)
        .clip(lower=0, upper=100)
        .round()
        .astype("Int64")
    )
    result["display_news"] = (
        news.str.replace(NEWS_CHANCE_PATTERN, "", regex=True).str.strip()
    )
    return result
