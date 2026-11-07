import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from host_games import ACTIVE_STATUSES, HostGames
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class HostGamesTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.query = self.db.table.return_value
        for name in ["select", "in_", "order", "range", "update", "eq"]:
            getattr(self.query, name).return_value = self.query
        self.manager = HostGames(self.db, "host-password")

    def test_wrong_or_empty_password_cannot_read_resume_or_close(self):
        for password in ["", "wrong"]:
            for operation, args in [(self.manager.list_active, ()),
                                    (self.manager.resume, ("ABC123", "browser")),
                                    (self.manager.close, ("ABC123",))]:
                with self.assertRaises(PermissionError):
                    operation(password, *args)
        self.db.table.assert_not_called()
        self.assertFalse(HostGames(self.db, "").authorized(""))
        self.assertTrue(HostGames(self.db, "árvíz").authorized("árvíz"))

    def test_lists_active_games_including_disconnected_hosts(self):
        game = {"game_code": "ABC123", "host_id": None}
        self.query.execute.return_value.data = [game]
        self.assertEqual(self.manager.list_active("host-password"), [game])
        self.query.in_.assert_called_once_with("game_status", ACTIVE_STATUSES)
        self.query.range.assert_called_once_with(0, 499)

    def test_listing_paginates(self):
        self.query.execute.side_effect = [SimpleNamespace(data=[{}] * 500), SimpleNamespace(data=[{}])]
        self.assertEqual(len(self.manager.list_active("host-password")), 501)
        self.assertEqual(self.query.range.call_args_list[1].args, (500, 999))

    def test_resume_claims_host_only_for_an_active_game(self):
        game = {"game_code": "ABC123", "teams": [{"name": "Kék"}]}
        self.query.execute.return_value.data = [game]
        self.assertEqual(self.manager.resume("host-password", "ABC123", "browser"), game)
        self.assertEqual(self.query.update.call_args.args[0]["host_id"], "browser")
        self.query.eq.assert_called_once_with("game_code", "ABC123")
        self.query.in_.assert_called_once_with("game_status", ACTIVE_STATUSES)

    def test_close_preserves_game_data_and_clears_host(self):
        self.query.execute.return_value.data = [{"game_code": "ABC123"}]
        self.manager.close("host-password", "ABC123")
        self.query.update.assert_called_once_with({"game_status": "closed", "host_id": None, "host_last_seen": None})
        self.query.eq.assert_called_once_with("game_code", "ABC123")
        self.query.in_.assert_called_once_with("game_status", ACTIVE_STATUSES)

    def test_game_closed_since_listing_cannot_be_resumed_or_closed_again(self):
        self.query.execute.return_value.data = []
        with self.assertRaises(ValueError):
            self.manager.resume("host-password", "ABC123", "browser")
        with self.assertRaises(ValueError):
            self.manager.close("host-password", "ABC123")

    def test_normal_join_rejects_closed_games(self):
        tree = ast.parse((ROOT / "streamlit_app.py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "load_shared_game")
        apply = MagicMock()
        ns = {"get_shared_game": lambda code: {"game_status": "closed"}, "apply_shared_game": apply}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "test", "exec"), ns)
        self.assertFalse(ns["load_shared_game"]("ABC123"))
        apply.assert_not_called()


class HostGamesUITests(unittest.TestCase):
    def make_app(self):
        tree = ast.parse((ROOT / "streamlit_app.py").read_text())
        definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name in {"render_host_games", "parse_utc", "host_is_alive"}]
        script = '''
import streamlit as st
from unittest.mock import MagicMock
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from host_games import HostGames
HOST_TIMEOUT_SECONDS = 20
if "db" not in st.session_state:
    db = MagicMock()
    query = db.table.return_value
    for name in ["select", "in_", "order", "range", "update", "eq"]:
        getattr(query, name).return_value = query
    query.execute.return_value.data = [{
        "game_code": "ABC123", "game_status": "playing", "number_of_teams": 1,
        "teams": [{"name": "Kék csapat", "year_points": 4}],
        "host_id": None, "host_last_seen": None,
    }]
    st.session_state.db = db
    st.session_state.device_id = "browser"
supabase = st.session_state.db
def apply_shared_game(game):
    st.session_state.game_started = True
    st.session_state.restored_game = game
'''
        script += ast.unparse(ast.Module(body=definitions, type_ignores=[]))
        script += '\nif not st.session_state.get("game_started", False):\n    render_host_games()\nelse:\n    st.success("Restored")\n'
        app = AppTest.from_string(script)
        app.secrets["HOST_PASSWORD"] = "host-password"
        return app.run()

    def test_list_is_hidden_until_password_is_valid(self):
        app = self.make_app()
        self.assertFalse(app.exception)
        app.session_state.db.table.assert_not_called()
        app.text_input(key="manage_host_password").set_value("wrong")
        app.button(key="manage_games_refresh").click().run()
        self.assertFalse(app.exception)
        app.session_state.db.table.assert_not_called()
        self.assertTrue(app.error)
        app.text_input(key="manage_host_password").set_value("host-password")
        app.button(key="manage_games_refresh").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("ABC123" in title.value for title in app.subheader))
        app.text_input(key="manage_host_password").set_value("").run()
        self.assertFalse(any("ABC123" in title.value for title in app.subheader))

    def test_reconnect_without_entering_game_code(self):
        app = self.make_app()
        app.text_input(key="manage_host_password").set_value("host-password")
        app.button(key="manage_games_refresh").click().run()
        app.button(key="manage_resume_ABC123").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.game_code, "ABC123")
        self.assertTrue(app.session_state.is_host)
        self.assertTrue(app.session_state.host_authenticated)

    def test_close_confirmation_updates_only_the_selected_game(self):
        app = self.make_app()
        app.text_input(key="manage_host_password").set_value("host-password")
        app.button(key="manage_games_refresh").click().run()
        query = app.session_state.db.table.return_value
        query.update.assert_not_called()
        existing = query.execute.return_value.data
        query.execute.side_effect = [SimpleNamespace(data=existing),
                                     SimpleNamespace(data=[{"game_code": "ABC123"}]),
                                     SimpleNamespace(data=[])]
        app.button(key="manage_close_ABC123").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("lezártad" in item.value for item in app.success))
        self.assertTrue(any("Nincs folyamatban" in item.value for item in app.info))
        query.update.assert_called_once_with({"game_status": "closed", "host_id": None, "host_last_seen": None})
        query.eq.assert_called_once_with("game_code", "ABC123")


if __name__ == "__main__":
    unittest.main()
