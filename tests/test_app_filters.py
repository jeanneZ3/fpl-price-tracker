from streamlit.testing.v1 import AppTest

from src.database.database_setup import get_connection


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
        if button.label == "Add All Players From Selected Teams"
    )
    bulk_add_button.click().run(timeout=30)

    selected_player_ids = set(app.sidebar.multiselect[2].value)
    assert palmer_ids["Chelsea"] in selected_player_ids
    assert palmer_ids["Ipswich Town"] not in selected_player_ids
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

    assert app.sidebar.multiselect[0].value == sorted(
        ["GKP", "DEF", "MID", "FWD"]
    )
    assert len(app.sidebar.multiselect[1].value) > 1
    assert app.sidebar.multiselect[2].value == imported_player_ids
    assert not app.exception
