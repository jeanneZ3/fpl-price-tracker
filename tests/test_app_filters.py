from streamlit.testing.v1 import AppTest

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
        "message": "Imported test squad.",
    }
    app.run(timeout=30)

    assert app.sidebar.multiselect[0].value == []
    assert app.sidebar.multiselect[1].value == []
    assert app.sidebar.multiselect[2].value == imported_player_ids
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


def test_chart_view_switches_between_one_price_or_points_visual():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    chart_view = app.segmented_control[0]
    assert chart_view.label == "Chart view"
    assert chart_view.options == ["Price", "Points"]
    assert chart_view.value == "Price"
    assert len(app.get("vega_lite_chart")) == 1
    assert "Price Over Gameweeks" in [heading.value for heading in app.subheader]

    chart_view.set_value("Points").run(timeout=30)

    assert app.segmented_control[0].value == "Points"
    assert len(app.get("vega_lite_chart")) == 1
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
