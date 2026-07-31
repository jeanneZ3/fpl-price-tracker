import pytest

from src.dashboard.search_helpers import (
    normalize_search_text,
    player_name_matches,
    transliterate_search_text,
)


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Ødegaard", "odegaard"),
        ("Šeško", "sesko"),
        ("João Pedro", "joao pedro"),
        ("Muñoz", "munoz"),
        ("Groß", "gross"),
        ("Højlund", "hojlund"),
    ],
)
def test_normalize_search_text_handles_player_name_variants(original, expected):
    assert normalize_search_text(original) == expected


def test_transliterate_search_text_preserves_display_case():
    assert transliterate_search_text("Ødegaard") == "Odegaard"
    assert transliterate_search_text("João Pedro") == "Joao Pedro"


@pytest.mark.parametrize(
    ("player_name", "query"),
    [
        ("Ødegaard", "Odegaard"),
        ("Šeško", "sesko"),
        ("João Pedro", "joao"),
        ("João Pedro", "pedro joao"),
    ],
)
def test_player_name_matches_without_requiring_accents(player_name, query):
    assert player_name_matches(player_name, query)


def test_player_name_match_still_rejects_different_name():
    assert not player_name_matches("Ødegaard", "Odegard")
