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
    app.sidebar.button[0].click().run(timeout=30)

    selected_player_ids = set(app.sidebar.multiselect[2].value)
    assert palmer_ids["Chelsea"] in selected_player_ids
    assert palmer_ids["Ipswich Town"] not in selected_player_ids
    assert not app.exception
