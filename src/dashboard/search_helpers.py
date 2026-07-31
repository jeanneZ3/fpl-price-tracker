"""Helpers for forgiving, accent-insensitive player-name search."""

import unicodedata


SPECIAL_LETTER_TRANSLATION = str.maketrans(
    {
        "Æ": "AE",
        "æ": "ae",
        "Ð": "D",
        "ð": "d",
        "Đ": "D",
        "đ": "d",
        "Ł": "L",
        "ł": "l",
        "Ø": "O",
        "ø": "o",
        "Œ": "OE",
        "œ": "oe",
        "Þ": "Th",
        "þ": "th",
        "ß": "ss",
        "ẞ": "SS",
        "ı": "i",
    }
)


def transliterate_search_text(value: object) -> str:
    """Return text with accents and special letters converted to ASCII forms."""
    translated = str(value or "").translate(SPECIAL_LETTER_TRANSLATION)
    decomposed = unicodedata.normalize("NFKD", translated)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def normalize_search_text(value: object) -> str:
    """Return a casefolded search form with accents and special letters removed."""
    return transliterate_search_text(value).casefold()


def player_name_matches(player_name: object, query: object) -> bool:
    """Return whether every normalized query term occurs in the player name."""
    normalized_name = normalize_search_text(player_name)
    return all(
        term in normalized_name
        for term in normalize_search_text(query).split()
    )
