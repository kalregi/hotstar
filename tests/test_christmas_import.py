import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import import_christmas as importer
from song_catalog import filter_songs, load_songs


ROOT = Path(__file__).resolve().parents[1]


class ChristmasImportTests(unittest.TestCase):
    def test_christmas_pool_has_150_resolved_recordings_and_language_filters(self):
        songs = load_songs(ROOT / "songs.csv")
        christmas = filter_songs(songs, ["Karácsonyi slágerek"])
        self.assertEqual(len(christmas), 150)
        self.assertEqual(len({s["spotify_uri"] for s in christmas}), 150)
        self.assertEqual(len(filter_songs(songs, ["Karácsonyi slágerek"], [], ["hu"])), 20)
        self.assertEqual(len(filter_songs(songs, ["Karácsonyi slágerek"], [], ["international"])), 130)
        self.assertTrue(all(s["difficulty"] in (1, 2, 3) for s in christmas))

    def test_same_title_from_wrong_artist_is_not_accepted(self):
        row = {"artist": "Mariah Carey", "title": "All I Want for Christmas Is You"}
        track = {"name": row["title"], "artists": [{"name": "Karaoke All Stars"}]}
        title, artist = importer.candidate_scores(row, track)
        self.assertEqual(title, 100)
        self.assertLess(artist, 85)
        for suffix in (" - Live", " - Remix", " - Karaoke", " - Rehearsal", " - Demo"):
            track.update(name=row["title"] + suffix, artists=[{"name": row["artist"]}])
            self.assertEqual(importer.candidate_scores(row, track), (0, 0))

    def test_numeric_titles_are_not_discarded_as_remaster_years(self):
        row = {"artist": "The Smashing Pumpkins", "title": "1979"}
        track = {"name": "1979 - Remastered 2012", "artists": [{"name": row["artist"]}]}
        self.assertEqual(importer.candidate_scores(row, track), (100, 100))

    def test_metadata_suffix_and_verified_artist_alias(self):
        row = {"artist": "The Pogues", "title": "Fairytale of New York"}
        track = {"name": "Fairytale of New York (feat. Kirsty MacColl)",
                 "artists": [{"name": "The Pogues"}, {"name": "Kirsty MacColl"}]}
        self.assertEqual(importer.candidate_scores(row, track), (100, 100))
        row = {"artist": "Bojtorján", "title": "Karácsony este"}
        track = {"name": row["title"], "artists": [{"name": "Bojtorjan Ensemble"}]}
        self.assertEqual(importer.candidate_scores(row, track), (100, 100))

    def test_merge_is_repeatable_and_preserves_existing_song_data(self):
        source, _ = importer.read_rows(ROOT / "christmas_catalog.csv")
        matches, _ = importer.read_rows(ROOT / "reports/christmas_spotify_matches.csv")
        # A small existing library includes one shared recording with a different
        # style/difficulty; importing must preserve those curated attributes.
        existing = {key: source[0][key] for key in source[0]}
        existing.update(spotify_uri=matches[0]["spotify_uri"], style="Pop", difficulty="2")
        with tempfile.TemporaryDirectory() as folder:
            catalog = Path(folder) / "songs.csv"
            importer.save_rows(catalog, [existing], list(existing))
            with patch.object(importer, "CATALOG", catalog):
                importer.merge()
                first, _ = importer.read_rows(catalog)
                self.assertEqual(len(first), 150)
                self.assertEqual(first[0]["style"], "Pop / Karácsonyi slágerek")
                for field in existing:
                    if field != "style":
                        self.assertEqual(first[0][field], existing[field])
                importer.merge()
                second, _ = importer.read_rows(catalog)
                self.assertEqual(first, second)

    def test_unresolved_input_leaves_catalog_untouched(self):
        matches, fields = importer.read_rows(ROOT / "reports/christmas_spotify_matches.csv")
        matches[0]["spotify_match_status"] = "needs_review"
        with tempfile.TemporaryDirectory() as folder:
            catalog = Path(folder) / "songs.csv"
            catalog.write_text("untouched", encoding="utf-8")
            result = Path(folder) / "matches.csv"
            importer.save_rows(result, matches, fields)
            with patch.object(importer, "CATALOG", catalog), patch.object(importer, "RESULT", result):
                with self.assertRaisesRegex(ValueError, "Unresolved recording"):
                    importer.merge()
                self.assertEqual(catalog.read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()
