import json

from streamlit.testing.v1 import AppTest

from src.dashboard.chart_helpers import get_team_color
from src.database.database_setup import get_connection


def test_default_selection_is_the_full_arsenal_squad():
    conn = get_connection()
    try:
        arsenal_player_ids = {
            row[0]
            for row in conn.execute(
                "SELECT player_id FROM players WHERE team = 'Arsenal'"
            ).fetchall()
        }
    finally:
        conn.close()

    app = AppTest.from_file("app/app.py").run(timeout=30)

    assert set(app.session_state["players_to_compare"]) == arsenal_player_ids
    assert set(app.session_state["players_to_compare_draft"]) == arsenal_player_ids
    assert not app.exception


def test_hero_capitalizes_gameweek():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    hero = next(
        markdown.value
        for markdown in app.markdown
        if '<div class="fpl-hero">' in markdown.value
        and "Compare FPL player prices" in markdown.value
    )

    assert "Gameweek points" in hero
    assert "Data through Gameweek 2" in hero
    assert "gameweek points" not in hero
    assert "Data through gameweek" not in hero


def test_bulk_team_selection_uses_player_ids_for_duplicate_names():
    conn = get_connection()
    try:
        palmer_rows = conn.execute(
            """
            SELECT player_id, team
            FROM players
            WHERE web_name = 'Palmer'
            """
        ).fetchall()
    finally:
        conn.close()

    palmer_ids = {team: player_id for player_id, team in palmer_rows}
    assert {"Chelsea", "Ipswich Town"} <= palmer_ids.keys()

    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.sidebar.multiselect[1].set_value(["Chelsea"]).run(timeout=30)
    bulk_add_button = next(
        button
        for button in app.sidebar.button
        if button.label == "Select Matches"
    )
    bulk_add_button.click().run(timeout=30)

    selected_player_ids = set(app.sidebar.multiselect[2].value)
    assert palmer_ids["Chelsea"] in selected_player_ids
    assert palmer_ids["Ipswich Town"] not in selected_player_ids

    apply_button = next(
        button
        for button in app.sidebar.button
        if button.label == "Update Dashboard"
    )
    apply_button.click().run(timeout=30)

    applied_player_ids = set(app.session_state["players_to_compare"])
    assert palmer_ids["Chelsea"] in applied_player_ids
    assert palmer_ids["Ipswich Town"] not in applied_player_ids
    assert not app.exception


def test_imported_squad_replaces_selection_and_resets_filters():
    conn = get_connection()
    try:
        imported_player_ids = [
            row[0]
            for row in conn.execute(
                "SELECT player_id FROM players ORDER BY player_id LIMIT 15"
            ).fetchall()
        ]
    finally:
        conn.close()

    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.sidebar.multiselect[0].set_value(["GKP"]).run(timeout=30)
    app.sidebar.multiselect[1].set_value(["Arsenal"]).run(timeout=30)
    app.session_state["_pending_imported_squad"] = {
        "player_ids": imported_player_ids,
        "picks_by_gameweek": {1: tuple(imported_player_ids)},
        "message": "Imported test squad.",
    }
    app.run(timeout=30)

    assert app.sidebar.multiselect[0].value == []
    assert app.sidebar.multiselect[1].value == []
    assert app.sidebar.multiselect[2].value == imported_player_ids
    assert app.session_state["_selection_source"] == "imported"
    assert app.segmented_control[1].label == "Positions shown"
    assert app.segmented_control[1].value == "All"
    assert app.segmented_control[2].label == "Average using"
    assert app.segmented_control[2].options == [
        "Weeks in your squad",
        "All gameweeks",
    ]
    assert not app.exception


def test_position_filter_switches_imported_squad_without_changing_selection():
    conn = get_connection()
    try:
        imported_rows = conn.execute(
            """
            SELECT player_id, position, team
            FROM players
            ORDER BY player_id
            LIMIT 15
            """
        ).fetchall()
    finally:
        conn.close()

    imported_player_ids = [player_id for player_id, _, _ in imported_rows]
    defender_teams = {
        team for _, position, team in imported_rows if position == "DEF"
    }
    midfielder_teams = {
        team for _, position, team in imported_rows if position == "MID"
    }
    defender_count = sum(position == "DEF" for _, position, _ in imported_rows)
    midfielder_count = sum(position == "MID" for _, position, _ in imported_rows)
    assert defender_count > 0
    assert midfielder_count > 0

    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.session_state["_pending_imported_squad"] = {
        "player_ids": imported_player_ids,
        "picks_by_gameweek": {1: tuple(imported_player_ids)},
        "message": "Imported test squad.",
    }
    app.run(timeout=30)

    position_filter = next(
        control
        for control in app.segmented_control
        if control.label == "Positions shown"
    )
    assert position_filter.options == [
        "All positions",
        "Goalkeepers",
        "Defenders",
        "Midfielders",
        "Forwards",
    ]

    position_filter.set_value("DEF").run(timeout=30)

    assert app.session_state["players_to_compare"] == imported_player_ids
    assert len(app.dataframe[0].value) == defender_count
    assert set(app.dataframe[0].value["Pos"]) == {"DEF"}
    assert any(
        caption.value
        == f"Showing {defender_count} of 15 selected players. "
        "Your full selection is unchanged."
        for caption in app.caption
    )
    defender_legends = [
        markdown.value
        for markdown in app.markdown
        if "data-palette-version" in markdown.value
    ]
    assert len(defender_legends) == 2
    assert all(">Team<" in legend for legend in defender_legends)
    assert all(
        all(team in legend for team in defender_teams)
        for legend in defender_legends
    )
    trend_spec = json.loads(app.get("vega_lite_chart")[0].proto.spec)
    trend_colors = {
        layer["mark"].get("color")
        for layer in trend_spec["layer"]
        if isinstance(layer.get("mark"), dict)
    }
    assert {get_team_color(team) for team in defender_teams} <= trend_colors
    scatter_spec = json.loads(app.get("vega_lite_chart")[1].proto.spec)
    scatter_colors = {
        layer["mark"].get("color")
        for layer in scatter_spec["layer"]
        if isinstance(layer.get("mark"), dict)
    }
    assert {get_team_color(team) for team in defender_teams} <= scatter_colors

    next(
        control
        for control in app.segmented_control
        if control.label == "Positions shown"
    ).set_value("MID").run(timeout=30)

    assert app.session_state["players_to_compare"] == imported_player_ids
    assert len(app.dataframe[0].value) == midfielder_count
    assert set(app.dataframe[0].value["Pos"]) == {"MID"}
    midfielder_legends = [
        markdown.value
        for markdown in app.markdown
        if "data-palette-version" in markdown.value
    ]
    assert len(midfielder_legends) == 2
    assert all(">Team<" in legend for legend in midfielder_legends)
    assert all(
        all(team in legend for team in midfielder_teams)
        for legend in midfielder_legends
    )
    assert not app.exception


def test_sidebar_selection_actions_are_clear_and_work():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    assert len(app.sidebar.expander) == 1
    assert app.sidebar.expander[0].label == "Option 2: Select players manually"
    assert [button.label for button in app.sidebar.expander[0].button] == [
        "Select Matches",
        "Clear Players",
        "✓ Dashboard Updated",
    ]
    assert [button.label for button in app.sidebar.button] == [
        "Import Your Squad",
        "Select Matches",
        "Clear Players",
        "✓ Dashboard Updated",
    ]

    clear_button = next(
        button for button in app.sidebar.button if button.label == "Clear Players"
    )
    clear_button.click().run(timeout=30)

    assert app.sidebar.multiselect[2].value == []
    assert not app.exception


def test_chart_view_switches_while_price_score_scatter_remains_visible():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    chart_view = app.segmented_control[0]
    assert chart_view.label == "Chart view"
    assert chart_view.options == ["Price", "Points"]
    assert chart_view.value == "Price"
    assert len(app.get("vega_lite_chart")) == 2
    assert "Price Over Gameweeks" in [heading.value for heading in app.subheader]
    assert "Average Price vs. Average Score" in [
        heading.value for heading in app.subheader
    ]
    scatter_spec = json.loads(app.get("vega_lite_chart")[1].proto.spec)
    scatter_encoding = scatter_spec["layer"][0]["encoding"]
    assert scatter_encoding["x"]["field"] == "average_score"
    assert "datum.value < 0" in scatter_encoding["x"]["axis"]["labelExpr"]
    assert scatter_encoding["y"]["field"] == "average_price"
    assert scatter_encoding["y"]["scale"]["reverse"] is True

    chart_view.set_value("Points").run(timeout=30)

    assert app.segmented_control[0].value == "Points"
    assert len(app.get("vega_lite_chart")) == 2
    assert "Points Over Gameweeks" in [heading.value for heading in app.subheader]
    assert not app.exception


def test_manual_player_changes_wait_for_apply_button():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    original_selection = list(app.session_state["players_to_compare"])
    new_selection_label = [app.sidebar.multiselect[2].options[-1]]

    app.sidebar.multiselect[2].set_value(new_selection_label).run(timeout=30)
    new_selection_ids = list(app.sidebar.multiselect[2].value)

    assert app.session_state["players_to_compare"] == original_selection
    assert app.session_state["players_to_compare_draft"] == new_selection_ids

    apply_button = next(
        button
        for button in app.sidebar.button
        if button.label == "Update Dashboard"
    )
    apply_button.click().run(timeout=30)

    assert app.session_state["players_to_compare"] == new_selection_ids
    assert app.session_state["_selection_source"] == "manual"
    assert len(app.segmented_control) == 2
    assert app.session_state["comparison_position_filter"] == "All"
    assert not app.exception


def test_player_picker_exposes_english_alias_and_keeps_original_selected_name():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.sidebar.multiselect[2].set_value([]).run(timeout=30)

    odegaard_option = next(
        option
        for option in app.sidebar.multiselect[2].options
        if "Search: Odegaard" in option
    )
    assert odegaard_option == "Ødegaard (Arsenal) · Search: Odegaard"

    app.sidebar.multiselect[2].set_value([odegaard_option]).run(timeout=30)

    assert "Ødegaard (Arsenal)" in app.sidebar.multiselect[2].options
    assert app.sidebar.multiselect[2].value == [15]
    assert not app.exception
