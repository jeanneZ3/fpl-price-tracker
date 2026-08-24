"""Pure data preparation for the dashboard's price-versus-score scatterplot."""

import pandas as pd


def prepare_price_score_averages(
    history: pd.DataFrame,
    ownership_by_gameweek: dict[int, tuple[int, ...]] | None = None,
) -> pd.DataFrame:
    """Average price and GW points, optionally only for gameweeks a player was owned."""
    included_history = history.copy()
    if ownership_by_gameweek is not None:
        ownership_rows = [
            {"gameweek": int(gameweek), "player_id": int(player_id)}
            for gameweek, player_ids in ownership_by_gameweek.items()
            for player_id in player_ids
        ]
        if not ownership_rows:
            return pd.DataFrame()
        ownership = pd.DataFrame(ownership_rows).drop_duplicates()
        included_history = included_history.merge(
            ownership, on=["gameweek", "player_id"], how="inner"
        )

    if included_history.empty:
        return pd.DataFrame()

    averages = (
        included_history.groupby(
            ["player_id", "web_name", "team", "position", "position_label"],
            as_index=False,
        )
        .agg(
            average_price=("price", "mean"),
            average_score=("event_points", "mean"),
            gameweeks_included=("gameweek", "nunique"),
        )
    )

    duplicate_names = {
        name
        for name, count in averages.groupby("web_name")["player_id"].nunique().items()
        if count > 1
    }
    averages["chart_name"] = averages["web_name"]
    duplicate_mask = averages["web_name"].isin(duplicate_names)
    averages.loc[duplicate_mask, "chart_name"] = (
        averages.loc[duplicate_mask, "web_name"]
        + " ("
        + averages.loc[duplicate_mask, "team"]
        + ")"
    )
    return averages
