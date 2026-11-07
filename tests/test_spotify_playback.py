import unittest
from unittest.mock import Mock, patch

from spotify_playback import PlaybackError, start_game_song, stop_album_continuation


URI = "spotify:track:" + "a" * 22
ALBUM = "spotify:album:" + "b" * 22


class SpotifyPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.spotify = Mock()
        self.spotify.devices.return_value = {"devices": [
            {"id": "other", "is_active": False},
            {"id": "mac", "is_active": True, "is_restricted": False},
        ]}
        self.spotify.track.return_value = {
            "uri": URI, "is_playable": True, "duration_ms": 180000,
            "album": {"uri": ALBUM},
        }
        self.playback = {
            "is_playing": True, "device": {"id": "mac"}, "progress_ms": 500,
            "item": {"uri": URI, "duration_ms": 180000}, "context": {"uri": ALBUM},
        }
        self.spotify.current_playback.return_value = self.playback
        self.sleep = patch("spotify_playback.time.sleep").start()
        self.clock = patch("spotify_playback.time.monotonic", return_value=100).start()
        self.addCleanup(patch.stopall)

    def test_album_offset_targets_active_device_and_confirms_actual_playback(self):
        self.spotify.current_playback.side_effect = [None, self.playback]
        guard = start_game_song(self.spotify, {"spotify_uri": URI})
        self.spotify.start_playback.assert_called_once_with(
            device_id="mac", position_ms=0, context_uri=ALBUM, offset={"uri": URI}
        )
        self.assertEqual(guard["device_id"], "mac")
        self.assertEqual(guard["check_at"], 279.5)

    def test_silent_success_is_reported_as_failure(self):
        self.spotify.current_playback.return_value = {"is_playing": False, "item": None}
        with self.assertRaisesRegex(PlaybackError, "nem kezdett el"):
            start_game_song(self.spotify, {"spotify_uri": URI})

    def test_wrong_device_or_track_is_not_success(self):
        self.spotify.current_playback.return_value = {**self.playback, "device": {"id": "other"}}
        with self.assertRaises(PlaybackError):
            start_game_song(self.spotify, {"spotify_uri": URI})

    def test_missing_active_device_does_not_start_on_someone_elses_computer(self):
        self.spotify.devices.return_value = {"devices": [{"id": "other", "is_active": False}]}
        with self.assertRaisesRegex(PlaybackError, "Nincs aktív"):
            start_game_song(self.spotify, {"spotify_uri": URI})
        self.spotify.start_playback.assert_not_called()

    def test_unplayable_or_invalid_song_does_not_interrupt_playback(self):
        with self.assertRaises(PlaybackError):
            start_game_song(self.spotify, {"spotify_uri": ""})
        self.spotify.track.return_value["is_playable"] = False
        with self.assertRaises(PlaybackError):
            start_game_song(self.spotify, {"spotify_uri": URI})
        self.spotify.start_playback.assert_not_called()

    def test_relinked_track_can_be_verified(self):
        linked = "spotify:track:" + "c" * 22
        self.spotify.track.return_value["uri"] = linked
        self.spotify.current_playback.return_value = {
            **self.playback, "item": {"uri": linked, "linked_from": {"uri": URI}}
        }
        guard = start_game_song(self.spotify, {"spotify_uri": URI})
        self.assertEqual(set(guard["accepted_uris"]), {URI, linked})

    def test_guard_does_not_poll_during_song(self):
        guard = {"device_id": "mac", "album_uri": ALBUM, "accepted_uris": [URI], "check_at": 200}
        self.assertEqual(stop_album_continuation(self.spotify, guard), guard)
        self.spotify.current_playback.assert_not_called()

    def test_guard_pauses_next_album_song(self):
        guard = {"device_id": "mac", "album_uri": ALBUM, "accepted_uris": [URI], "check_at": 99}
        self.spotify.current_playback.return_value = {**self.playback, "item": {"uri": "next"}}
        self.assertIsNone(stop_album_continuation(self.spotify, guard))
        self.spotify.pause_playback.assert_called_once_with(device_id="mac")

    def test_guard_does_not_pause_another_context_or_device(self):
        guard = {"device_id": "mac", "album_uri": ALBUM, "accepted_uris": [URI], "check_at": 99}
        self.spotify.current_playback.return_value = {
            **self.playback, "item": {"uri": "next"}, "context": {"uri": "different"}
        }
        self.assertIsNone(stop_album_continuation(self.spotify, guard))
        self.spotify.pause_playback.assert_not_called()

    def test_guard_recalculates_after_seeking(self):
        guard = {"device_id": "mac", "album_uri": ALBUM, "accepted_uris": [URI], "check_at": 99}
        result = stop_album_continuation(self.spotify, guard)
        self.assertGreater(result["check_at"], 100)
        self.spotify.pause_playback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
