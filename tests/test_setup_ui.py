"""Exercise the real creation form without contacting Spotify or Supabase."""

import ast
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest
from song_catalog import load_songs


ROOT = Path(__file__).resolve().parents[1]


class SetupUITests(unittest.TestCase):
    def make_app(self):
        tree = ast.parse((ROOT / "streamlit_app.py").read_text())
        form = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.With)
                    and isinstance(node.items[0].context_expr, ast.Name)
                    and node.items[0].context_expr.id == "create_tab")
        defaults = [node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name)
                            and target.id in {"DECADES", "DEFAULT_DECADE_COUNTS", "DECADE_PRESETS"}
                            for target in node.targets)]
        callbacks = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == "clamp_decade_selection"]
        script = (
            "import streamlit as st\n"
            "from song_catalog import load_songs, available_styles, filter_songs\n"
            f"SONGS = load_songs({str(ROOT / 'songs.csv')!r})\n"
            "STYLES = available_styles(SONGS)\n"
            + ast.unparse(ast.Module(body=defaults + callbacks + form.body, type_ignores=[]))
        )
        return AppTest.from_string(script).run()

    def test_filter_changes_update_limits_and_allow_empty_decades(self):
        app = self.make_app()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.multiselect), 3)
        app.multiselect(key="setup_difficulties").set_value([1, 2])
        app.multiselect(key="setup_languages").set_value(["hu"])
        app.multiselect(key="setup_style_groups").set_value(["Rock / Alternative"])
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(all(slider.value <= slider.max for slider in app.slider))
        self.assertTrue(any("1950s — nincs dal" in caption.value for caption in app.caption))
        app.multiselect(key="setup_difficulties").set_value([3])
        app.multiselect(key="setup_languages").set_value(["hu", "international"])
        app.run()
        self.assertFalse(app.exception)
        app.multiselect(key="setup_difficulties").set_value([])
        app.multiselect(key="setup_languages").set_value([])
        app.multiselect(key="setup_style_groups").set_value([])
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.slider), 8)
        self.assertTrue(any(f"{len(load_songs(ROOT / 'songs.csv'))} dal" in caption.value for caption in app.caption))

    def test_presets_replace_manual_counts_and_respect_filtered_availability(self):
        app = self.make_app()
        presets = {
            "Régebbi": [10, 20, 30, 25, 15, 10, 5, 0],
            "Alapértelmezett": [5, 10, 15, 20, 20, 20, 15, 10],
            "Újabb": [0, 5, 10, 15, 20, 30, 25, 15],
        }
        for name, counts in presets.items():
            app.button(key=f"decade_preset_{name}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual([slider.value for slider in app.slider], counts)
            self.assertEqual(sum(slider.value for slider in app.slider), sum(counts))
        app.slider(key="decade_count_1990s").set_value(100).run()
        self.assertEqual(app.slider(key="decade_count_1990s").value, 100)
        app.button(key="decade_preset_Alapértelmezett").click().run()
        self.assertEqual([slider.value for slider in app.slider], presets["Alapértelmezett"])
        app.multiselect(key="setup_difficulties").set_value([3])
        app.multiselect(key="setup_languages").set_value(["hu"])
        app.run()
        for name, counts in presets.items():
            app.button(key=f"decade_preset_{name}").click().run()
            self.assertFalse(app.exception)
            for index, decade in enumerate(range(1950, 2030, 10)):
                key = f"decade_count_{decade}s"
                sliders = [slider for slider in app.slider if slider.key == key]
                available = int(sliders[0].label.rsplit(": ", 1)[1])
                expected = min(counts[index], available)
                self.assertEqual(app.session_state[key], expected)

    def test_sliders_share_a_scale_and_clamp_to_each_decades_pool(self):
        app = self.make_app()
        self.assertEqual(len(app.slider), 8)
        songs = load_songs(ROOT / "songs.csv")
        from collections import Counter
        maximum = max(Counter(song["decade"] for song in songs).values())
        self.assertEqual({slider.max for slider in app.slider}, {maximum})
        app.slider(key="decade_count_2020s").set_value(10)
        app.slider(key="decade_count_1980s").set_value(10)
        app.run()
        self.assertEqual(app.slider(key="decade_count_2020s").value, 10)
        self.assertEqual(app.slider(key="decade_count_1980s").value, 10)
        app.slider(key="decade_count_2020s").set_value(200).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.slider(key="decade_count_2020s").value,
                         sum(song["decade"] == "2020s" for song in songs))
        app.multiselect(key="setup_difficulties").set_value([3])
        app.multiselect(key="setup_languages").set_value(["hu"])
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.slider), 8)
        self.assertEqual(len({slider.max for slider in app.slider}), 1)
        self.assertTrue(app.slider(key="decade_count_1950s").disabled)
        self.assertEqual(app.slider(key="decade_count_1950s").value, 0)
        for slider in app.slider:
            available = int(slider.label.rsplit(": ", 1)[1])
            self.assertLessEqual(slider.value, available)

    def test_all_mode_tracks_filter_changes_and_other_presets_restore_manual_controls(self):
        app = self.make_app()
        app.button(key="decade_preset_Összes").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(all(slider.disabled for slider in app.slider))
        self.assertEqual(sum(slider.value for slider in app.slider), len(load_songs(ROOT / "songs.csv")))
        app.multiselect(key="setup_style_groups").set_value(["Karácsonyi slágerek"]).run()
        self.assertFalse(app.exception)
        self.assertEqual(sum(slider.value for slider in app.slider), 150)
        app.multiselect(key="setup_languages").set_value(["hu"]).run()
        self.assertEqual(sum(slider.value for slider in app.slider), 20)
        app.multiselect(key="setup_languages").set_value([]).run()
        self.assertEqual(sum(slider.value for slider in app.slider), 150)
        app.button(key="decade_preset_Alapértelmezett").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state["setup_all_decades"])
        self.assertTrue(any(not slider.disabled for slider in app.slider))


if __name__ == "__main__":
    unittest.main()
