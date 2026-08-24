import pandas as pd
import pytest

from src.dashboard.chart_helpers import (
    POSITION_COLORS,
    POSITION_ORDER,
    POSITION_SHAPES,
    TEAM_COLORS,
    build_position_color_scale,
    build_position_shape_scale,
    build_team_color_scale,
    compute_label_positions,
    compute_point_offsets,
    compute_price_movers,
    compute_summary_kpis,
    get_position_color,
    get_position_shape,
    get_team_color,
)
from src.dashboard.scatter_helpers import prepare_price_score_averages


class TestGetTeamColor:
    def test_known_team_returns_mapped_hex(self):
        assert get_team_color("Arsenal") == TEAM_COLORS["Arsenal"]

    def test_all_mapped_colors_are_valid_hex(self):
        for color in TEAM_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7
            int(color[1:], 16)  # raises ValueError if not valid hex

    def test_unknown_team_gets_a_valid_hex_fallback(self):
        color = get_team_color("Some Newly Promoted FC")
        assert color.startswith("#")
        assert len(color) == 7
        int(color[1:], 16)

    def test_unknown_team_fallback_is_deterministic(self):
        assert get_team_color("Some Newly Promoted FC") == get_team_color("Some Newly Promoted FC")

    def test_different_unknown_teams_get_different_colors(self):
        assert get_team_color("Team Alpha FC") != get_team_color("Team Beta FC")


class TestGetPositionShape:
    @pytest.mark.parametrize("position", POSITION_ORDER)
    def test_known_positions_are_mapped(self, position):
        assert get_position_shape(position) == POSITION_SHAPES[position]

    def test_positions_have_distinct_shapes(self):
        shapes = [POSITION_SHAPES[p] for p in POSITION_ORDER]
        assert len(set(shapes)) == len(shapes)

    def test_unknown_position_falls_back_to_circle(self):
        assert get_position_shape("???") == "circle"


class TestGetPositionColor:
    @pytest.mark.parametrize("position", POSITION_ORDER)
    def test_known_positions_are_mapped(self, position):
        assert get_position_color(position) == POSITION_COLORS[position]

    def test_positions_have_distinct_colors(self):
        colors = [POSITION_COLORS[p] for p in POSITION_ORDER]
        assert len(set(colors)) == len(colors)

    def test_all_mapped_colors_are_valid_hex(self):
        for color in POSITION_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7
            int(color[1:], 16)

    def test_unknown_position_falls_back_to_grey(self):
        assert get_position_color("???") == "#7F7F7F"


class TestScales:
    def test_team_color_scale_covers_every_team_once(self):
        teams = ["Chelsea", "Arsenal", "Chelsea", "Man City"]
        scale = build_team_color_scale(teams)
        assert scale.domain == sorted(set(teams))
        assert len(scale.range) == len(scale.domain)

    def test_position_shape_scale_matches_position_order(self):
        scale = build_position_shape_scale()
        assert scale.domain == POSITION_ORDER
        assert scale.range == [POSITION_SHAPES[p] for p in POSITION_ORDER]

    def test_position_color_scale_matches_position_order(self):
        scale = build_position_color_scale()
        assert scale.domain == POSITION_ORDER
        assert scale.range == [POSITION_COLORS[p] for p in POSITION_ORDER]


def _snapshot_frame(rows):
    return pd.DataFrame(
        rows, columns=["player_id", "web_name", "team", "gameweek", "price"]
    )


class TestComputeSummaryKpis:
    def test_empty_dataframe(self):
        kpis = compute_summary_kpis(pd.DataFrame(columns=["player_id", "team", "gameweek"]))
        assert kpis == {
            "players_tracked": 0,
            "teams_tracked": 0,
            "gameweeks_tracked": 0,
            "latest_gameweek": None,
        }

    def test_counts_unique_players_teams_and_gameweeks(self):
        df = _snapshot_frame(
            [
                (1, "A", "Arsenal", 0, 5.0),
                (2, "B", "Chelsea", 0, 6.0),
                (1, "A", "Arsenal", 1, 5.1),
                (2, "B", "Chelsea", 1, 6.0),
            ]
        )
        kpis = compute_summary_kpis(df)
        assert kpis["players_tracked"] == 2
        assert kpis["teams_tracked"] == 2
        assert kpis["gameweeks_tracked"] == 2
        assert kpis["latest_gameweek"] == 1


class TestComputePriceMovers:
    def test_single_gameweek_returns_no_movers(self):
        df = _snapshot_frame([(1, "A", "Arsenal", 0, 5.0), (2, "B", "Chelsea", 0, 6.0)])
        movers = compute_price_movers(df)
        assert movers == {"riser": None, "faller": None}

    def test_empty_dataframe_returns_no_movers(self):
        movers = compute_price_movers(pd.DataFrame(columns=["player_id", "web_name", "team", "gameweek", "price"]))
        assert movers == {"riser": None, "faller": None}

    def test_identifies_biggest_riser_and_faller(self):
        df = _snapshot_frame(
            [
                (1, "Riser", "Arsenal", 0, 5.0),
                (2, "Faller", "Chelsea", 0, 8.0),
                (3, "Flat", "Man City", 0, 6.0),
                (1, "Riser", "Arsenal", 1, 5.5),
                (2, "Faller", "Chelsea", 1, 7.5),
                (3, "Flat", "Man City", 1, 6.0),
            ]
        )
        movers = compute_price_movers(df)
        assert movers["riser"]["web_name"] == "Riser"
        assert movers["riser"]["delta"] == pytest.approx(0.5)
        assert movers["faller"]["web_name"] == "Faller"
        assert movers["faller"]["delta"] == pytest.approx(-0.5)

    def test_no_riser_when_all_prices_flat_or_falling(self):
        df = _snapshot_frame(
            [
                (1, "Flat", "Arsenal", 0, 5.0),
                (2, "Faller", "Chelsea", 0, 8.0),
                (1, "Flat", "Arsenal", 1, 5.0),
                (2, "Faller", "Chelsea", 1, 7.5),
            ]
        )
        movers = compute_price_movers(df)
        assert movers["riser"] is None
        assert movers["faller"]["web_name"] == "Faller"

    def test_ignores_players_missing_from_either_endpoint_gameweek(self):
        df = _snapshot_frame(
            [
                (1, "Continuous", "Arsenal", 0, 5.0),
                (1, "Continuous", "Arsenal", 1, 5.2),
                (2, "OnlyLater", "Chelsea", 1, 6.0),
            ]
        )
        movers = compute_price_movers(df)
        assert movers["riser"]["web_name"] == "Continuous"


class TestComputeLabelPositions:
    def test_empty_series_returned_unchanged(self):
        result = compute_label_positions(pd.Series(dtype=float), min_gap=0.2)
        assert result.empty

    def test_well_separated_values_are_untouched(self):
        values = pd.Series([4.0, 6.0, 8.0], index=["a", "b", "c"])
        result = compute_label_positions(values, min_gap=0.2)
        pd.testing.assert_series_equal(result, values, check_names=False)

    def test_clustered_values_are_pushed_apart_by_at_least_min_gap(self):
        values = pd.Series([5.0, 5.0, 5.0], index=["a", "b", "c"])
        result = compute_label_positions(values, min_gap=0.3)
        ordered = result.sort_values()
        gaps = ordered.diff().dropna()
        assert (gaps >= 0.3 - 1e-9).all()

    def test_preserves_original_index_and_order(self):
        values = pd.Series([5.0, 5.0], index=["second", "first"])
        result = compute_label_positions(values, min_gap=0.3)
        assert list(result.index) == ["second", "first"]

    def test_relative_order_of_values_is_preserved(self):
        values = pd.Series([5.0, 5.01, 4.99], index=["mid", "high", "low"])
        result = compute_label_positions(values, min_gap=0.3)
        assert result["low"] < result["mid"] < result["high"]

    def test_zero_or_negative_min_gap_returns_values_unchanged(self):
        values = pd.Series([5.0, 5.0], index=["a", "b"])
        result = compute_label_positions(values, min_gap=0)
        pd.testing.assert_series_equal(result, values, check_names=False)


class TestComputePointOffsets:
    def test_empty_series_returned_unchanged(self):
        result = compute_point_offsets(pd.Series(dtype=float), spacing=10.0)
        assert result.empty

    def test_unique_values_get_zero_offset(self):
        values = pd.Series([4.0, 5.0, 6.0], index=["a", "b", "c"])
        result = compute_point_offsets(values, spacing=10.0)
        assert (result == 0.0).all()

    def test_colliding_values_are_spread_symmetrically_around_zero(self):
        values = pd.Series([5.0, 5.0], index=["a", "b"])
        result = compute_point_offsets(values, spacing=10.0)
        assert set(result) == {-5.0, 5.0}
        assert result["a"] + result["b"] == 0.0

    def test_only_the_colliding_group_is_offset(self):
        values = pd.Series([5.0, 5.0, 9.0], index=["a", "b", "c"])
        result = compute_point_offsets(values, spacing=10.0)
        assert result["c"] == 0.0
        assert result["a"] != result["b"]

    def test_three_way_collision_centers_middle_entry_on_zero(self):
        values = pd.Series([5.0, 5.0, 5.0], index=["a", "b", "c"])
        result = compute_point_offsets(values, spacing=10.0)
        ordered = result.reindex(["a", "b", "c"])
        assert list(ordered) == [-10.0, 0.0, 10.0]


class TestPreparePriceScoreAverages:
    @staticmethod
    def history():
        return pd.DataFrame(
            [
                (1, "One", "Arsenal", "MID", "Midfielder", 1, 5.0, 2),
                (1, "One", "Arsenal", "MID", "Midfielder", 2, 5.2, 6),
                (2, "Two", "Chelsea", "FWD", "Forward", 1, 7.0, 1),
                (2, "Two", "Chelsea", "FWD", "Forward", 2, 7.4, 5),
            ],
            columns=[
                "player_id",
                "web_name",
                "team",
                "position",
                "position_label",
                "gameweek",
                "price",
                "event_points",
            ],
        )

    def test_all_gameweeks_average_price_and_gameweek_score(self):
        result = prepare_price_score_averages(self.history()).set_index("player_id")

        assert result.loc[1, "average_price"] == pytest.approx(5.1)
        assert result.loc[1, "average_score"] == pytest.approx(4.0)
        assert result.loc[1, "gameweeks_included"] == 2
        assert result.loc[2, "average_price"] == pytest.approx(7.2)
        assert result.loc[2, "average_score"] == pytest.approx(3.0)

    def test_owned_gameweeks_exclude_weeks_before_or_after_ownership(self):
        ownership = {1: (1,), 2: (2,)}

        result = prepare_price_score_averages(
            self.history(), ownership
        ).set_index("player_id")

        assert result.loc[1, "average_price"] == pytest.approx(5.0)
        assert result.loc[1, "average_score"] == pytest.approx(2.0)
        assert result.loc[1, "gameweeks_included"] == 1
        assert result.loc[2, "average_price"] == pytest.approx(7.4)
        assert result.loc[2, "average_score"] == pytest.approx(5.0)
        assert result.loc[2, "gameweeks_included"] == 1
