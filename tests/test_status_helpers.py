import pandas as pd

from src.dashboard.status_helpers import prepare_availability_display


def _availability_frame(rows):
    return pd.DataFrame(
        rows,
        columns=["status", "news", "chance_of_playing_this_round"],
    )


def test_moves_news_percentage_into_chance_column():
    result = prepare_availability_display(
        _availability_frame(
            [("d", "Hamstring injury - 75% chance of playing", None)]
        )
    )

    assert result.loc[0, "display_news"] == "Hamstring injury"
    assert result.loc[0, "display_chance"] == 75


def test_suspended_player_defaults_to_zero_and_keeps_news():
    result = prepare_availability_display(
        _availability_frame([("s", "Suspended until 6 Sep", None)])
    )

    assert result.loc[0, "display_news"] == "Suspended until 6 Sep"
    assert result.loc[0, "display_chance"] == 0


def test_available_player_defaults_to_one_hundred():
    result = prepare_availability_display(
        _availability_frame([("a", "", None)])
    )

    assert result.loc[0, "display_chance"] == 100


def test_structured_api_chance_takes_precedence_over_news():
    result = prepare_availability_display(
        _availability_frame(
            [("d", "Knock - 75% chance of playing", 50)]
        )
    )

    assert result.loc[0, "display_chance"] == 50


def test_unknown_doubtful_chance_remains_blank():
    result = prepare_availability_display(
        _availability_frame([("d", "Late fitness test", None)])
    )

    assert pd.isna(result.loc[0, "display_chance"])
