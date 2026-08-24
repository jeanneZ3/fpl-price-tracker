"""Backward-compatible imports for the public FPL squad importer."""

from src.api.squad_history_import import (
    ENTRY_URL,
    PICKS_URL,
    ImportedSquad,
    SquadImportError,
    fetch_latest_public_squad,
    parse_entry_id,
)

__all__ = [
    "ENTRY_URL",
    "PICKS_URL",
    "ImportedSquad",
    "SquadImportError",
    "fetch_latest_public_squad",
    "parse_entry_id",
]
