import ast
from collections import Counter
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from song_catalog import (
    available_styles,
    filter_songs,
    load_songs,
    sample_songs,
    shared_game_settings,
    song_style_groups,
    STYLE_GROUPS,
    style_tags,
)


ROOT = Path(__file__).resolve().parents[1]


class SessionState(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.songs = load_songs(ROOT / "songs.csv")

    def test_mixed_styles_and_rock_and_roll(self):
        self.assertEqual(style_tags(" Pop / Rock "), {"Pop", "Rock"})
        self.assertEqual(style_tags("Rock / Pop"), {"Pop", "Rock"})
        self.assertEqual(style_tags("Rock & Roll / Pop"), {"Rock", "Pop"})
        self.assertNotIn("Curated", available_styles(self.songs))

    def test_every_song_has_a_difficulty_and_duplicates_agree(self):
        self.assertTrue(self.songs)
        ratings = {}
        for song in self.songs:
            with self.subTest(artist=song["artist"], title=song["title"]):
                self.assertIn(song["difficulty"], (1, 2, 3))
                uri = song["spotify_uri"]
                if uri in ratings:
                    self.assertEqual(ratings[uri], song["difficulty"])
                ratings[uri] = song["difficulty"]

    def test_rock_includes_mixed_styles_but_not_plain_alternative(self):
        styles = ["Rock", "Pop / Rock", "Alternative / Rock", "Rock & Roll", "Alternative", "Pop"]
        songs = [{"style": style} for style in styles]
        self.assertEqual(filter_songs(songs, ["Rock"]), songs[:4])

    def test_multiple_styles_use_union_without_repeating_mixed_song(self):
        songs = [{"style": "Pop / Rock"}, {"style": "Dance"}, {"style": "Jazz"}]
        self.assertEqual(filter_songs(songs, ["Pop", "Rock", "Dance"]), songs[:2])
        self.assertEqual(filter_songs(songs, []), songs)

    def test_style_groups_cover_the_catalog(self):
        self.assertEqual(available_styles(self.songs), list(STYLE_GROUPS))
        self.assertEqual(
            filter_songs(self.songs, list(STYLE_GROUPS)), self.songs
        )
        self.assertEqual(song_style_groups("Curated"), {"Egyéb"})
        self.assertEqual(song_style_groups("Unknown"), {"Egyéb"})

    def test_groups_include_all_members_without_double_counting(self):
        self.assertEqual(song_style_groups("Alternative / Rock"), {"Rock / Alternative"})
        self.assertEqual(song_style_groups("Rock & Roll / Pop"), {"Rock / Alternative", "Pop"})
        songs = [{"style": "Alternative / Rock"}, {"style": "Alternative"}, {"style": "Pop"}]
        self.assertEqual(filter_songs(songs, ["Rock / Alternative"]), songs[:2])
        self.assertEqual(filter_songs(songs, ["Rock"]), songs[:1])
        self.assertEqual(song_style_groups("Disco / Funk"), {"Dance / Electronic / Disco", "Soul / R&B / Funk"})

    def test_grouped_sampling(self):
        selected = sample_songs(self.songs, {"1990s": 12}, ["Rock / Alternative"])
        self.assertEqual(len(selected), 12)
        self.assertTrue(all("Rock / Alternative" in song_style_groups(s["style"]) for s in selected))

    def test_difficulty_and_language_selections(self):
        for levels in ([1], [2], [3], [1, 2], [1, 3], [2, 3], [1, 2, 3], []):
            for languages in (["hu"], ["international"], ["hu", "international"], []):
                with self.subTest(levels=levels, languages=languages):
                    expected = [s for s in self.songs
                                if (not levels or s["difficulty"] in levels)
                                and (not languages or s["language"] in languages)]
                    self.assertEqual(filter_songs(self.songs, [], levels, languages), expected)

    def test_all_filters_intersect_and_empty_pool_is_safe(self):
        result = filter_songs(self.songs, ["Rock / Alternative", "Pop"], [1, 2], ["hu"])
        self.assertTrue(result)
        self.assertTrue(all(s["language"] == "hu" and s["difficulty"] in (1, 2)
                            and song_style_groups(s["style"]) & {"Rock / Alternative", "Pop"}
                            for s in result))
        self.assertEqual(filter_songs(self.songs, [], [99], ["hu"]), [])
        with self.assertRaisesRegex(ValueError, "csak 0 érhető el"):
            sample_songs(self.songs, {"1950s": 1}, [], [3], ["hu"])

    def test_all_mode_ignores_decade_quotas_and_keeps_other_filters(self):
        expected = filter_songs(self.songs, ["Karácsonyi slágerek"], [1, 2], ["hu"])
        selected = sample_songs(self.songs, {"1980s": 0}, ["Karácsonyi slágerek"], [1, 2], ["hu"], all_decades=True)
        self.assertCountEqual(selected, expected)

    def test_sample_respects_decades_and_styles(self):
        counts = {"1980s": 5, "1990s": 7, "2020s": 0}
        selected = sample_songs(self.songs, counts, ["Rock"])
        self.assertEqual(Counter(s["decade"] for s in selected), Counter({"1980s": 5, "1990s": 7}))
        self.assertTrue(all("Rock" in style_tags(s["style"]) for s in selected))
        self.assertEqual(len({id(s) for s in selected}), len(selected))

    def test_insufficient_filtered_pool_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "csak 0 érhető el"):
            sample_songs(self.songs, {"1950s": 1}, ["Afrobeats"])
        self.assertEqual(sample_songs(self.songs, {"1950s": 0}, ["Afrobeats"]), [])

    def test_shared_settings_survive_team_rotation_and_json_roundtrip(self):
        import json

        settings = {"decade_counts": {"1990s": 4}, "selected_styles": ["Rock"]}
        game = json.loads(json.dumps({"teams": [{}, {"game_settings": settings}]}))
        self.assertEqual(shared_game_settings(game), settings)
        self.assertIsNone(shared_game_settings({"teams": [{}]}))


class GameIntegrationTests(unittest.TestCase):
    def setUp(self):
        # Load the real game functions without running the app's Spotify/Supabase
        # connections or requiring production secrets during local tests.
        tree = ast.parse((ROOT / "streamlit_app.py").read_text())
        names = {
            "start_new_game", "start_rematch", "normalized_teams",
            "infer_team_order", "team_year_points", "team_tokens",
            "apply_shared_game",
        }
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.st = SimpleNamespace(session_state=SessionState(), error=Mock())
        self.update = Mock()
        self.ns = dict(
            st=self.st, random=random, SONGS=load_songs(ROOT / "songs.csv"),
            sample_songs=sample_songs, shared_game_settings=shared_game_settings,
            TEAM_STYLES=[{"emoji": "🔵", "color": "blue"}, {"emoji": "🟠", "color": "orange"}],
            COLOR_TEAM_NAMES=["Kék csapat", "Narancs csapat"],
            DEFAULT_DECADE_COUNTS={"1980s": 5, "1990s": 5},
            update_shared_game=self.update, sync_selected_team_identity=Mock(),
        )
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "streamlit_app.py", "exec"), self.ns)

    def test_creation_and_rematch_after_host_reconnect_keep_filters(self):
        counts = {"1980s": 5, "1990s": 7}
        self.assertTrue(self.ns["start_new_game"](2, counts, ["Rock"], [1, 2], ["hu"]))
        state = self.st.session_state
        game = dict(
            teams=state.teams, remaining_songs=state.remaining_songs,
            active_team_index=0, current_song=None, selected_position=None,
            revealed=False, last_result=None,
        )
        self.st.session_state = SessionState()
        self.ns["apply_shared_game"](game)
        self.assertEqual(self.st.session_state.selected_styles, ["Rock"])
        self.assertEqual(self.st.session_state.decade_counts, counts)
        self.assertEqual(self.st.session_state.selected_difficulties, [1, 2])
        self.assertEqual(self.st.session_state.selected_languages, ["hu"])
        for _ in range(2):
            self.assertTrue(self.ns["start_rematch"](game))
            update = self.update.call_args.kwargs
            selected = update["remaining_songs"] + [t["timeline"][0] for t in update["teams"]]
            self.assertEqual(Counter(s["decade"] for s in selected), Counter(counts))
            self.assertTrue(all("Rock" in style_tags(s["style"]) for s in selected))
            self.assertTrue(all(s["difficulty"] in (1, 2) and s["language"] == "hu" for s in selected))
            game.update(update)

    def test_style_only_saved_games_default_to_all_difficulties_and_languages(self):
        self.assertTrue(self.ns["start_new_game"](2, {"1980s": 5}, ["Rock"]))
        state = self.st.session_state
        game = dict(teams=state.teams, remaining_songs=state.remaining_songs,
                    active_team_index=0, current_song=None, selected_position=None,
                    revealed=False, last_result=None)
        settings = shared_game_settings(game)
        settings.pop("selected_difficulties")
        settings.pop("selected_languages")
        self.st.session_state = SessionState(selected_difficulties=[3], selected_languages=["hu"])
        self.ns["apply_shared_game"](game)
        self.assertEqual(self.st.session_state.selected_difficulties, [])
        self.assertEqual(self.st.session_state.selected_languages, [])
        self.assertTrue(self.ns["start_rematch"](game))

    def test_invalid_counts_do_not_start_or_update_a_game(self):
        self.assertFalse(self.ns["start_new_game"](2, {"1950s": 1}, ["Afrobeats"]))
        self.assertNotIn("teams", self.st.session_state)
        self.assertFalse(self.ns["start_new_game"](2, {"1990s": 1}, ["Rock"]))
        self.update.assert_not_called()

    def test_existing_games_can_still_start_rematches(self):
        self.assertTrue(self.ns["start_new_game"](2, {"1980s": 5}))
        teams = self.st.session_state.teams
        teams[0].pop("game_settings")
        self.st.session_state = SessionState()
        self.assertTrue(self.ns["start_rematch"]({"teams": teams}))
        self.update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
