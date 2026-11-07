from pathlib import Path
import unittest

from scripts.import_christmas import read_rows, identity
from song_catalog import load_songs, song_style_groups


ROOT = Path(__file__).resolve().parents[1]


class Rock90CatalogTests(unittest.TestCase):
    def test_expansion_contains_60_distinct_playable_90s_rock_recordings(self):
        source, _ = read_rows(ROOT / "rock_90s_catalog.csv")
        matches, _ = read_rows(ROOT / "reports/rock_90s_spotify_matches.csv")
        lookup = {identity(r): r for r in matches}
        songs = load_songs(ROOT / "songs.csv")
        self.assertEqual(len(source), 60)
        self.assertEqual(len({identity(row) for row in source}), 60)
        self.assertEqual(len({row["spotify_uri"] for row in source}), 60)
        self.assertEqual(sum(row["language"] == "hu" for row in source), 10)
        for row in source:
            with self.subTest(artist=row["artist"], title=row["title"]):
                self.assertTrue(1990 <= int(row["year"]) <= 1999)
                self.assertEqual(lookup[identity(row)]["spotify_match_status"], "ok")
                matching = [s for s in songs if s["spotify_uri"] == row["spotify_uri"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["year"], int(row["year"]))
                self.assertIn("Rock / Alternative", song_style_groups(matching[0]["style"]))
                self.assertIn(matching[0]["difficulty"], (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
