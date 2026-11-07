"""Verified Spotify playback, including the desktop track-start workaround."""

import re
import time


class PlaybackError(RuntimeError):
    pass


def start_game_song(spotify, song):
    uri = song.get("spotify_uri", "")
    if not re.fullmatch(r"spotify:track:[A-Za-z0-9]{22}", uri):
        raise PlaybackError("A dal Spotify-azonosítója hiányzik vagy hibás.")

    devices = spotify.devices().get("devices", [])
    device = next((d for d in devices if d.get("is_active")
                   and not d.get("is_restricted") and d.get("id")), None)
    if device is None:
        raise PlaybackError(
            "Nincs aktív, vezérelhető Spotify-eszköz. Nyisd meg a Spotifyt, "
            "indíts el benne kézzel egy dalt a kívánt eszközön, majd próbáld újra."
        )

    track = spotify.track(uri)
    if track.get("is_playable") is False or track.get("restrictions"):
        raise PlaybackError("Ez a Spotify-felvétel ezen a fiókon nem játszható le.")
    resolved_uri = track.get("uri") or uri
    accepted_uris = {uri, resolved_uri}
    album_uri = (track.get("album") or {}).get("uri")
    kwargs = {"device_id": device["id"], "position_ms": 0}
    # Some desktop clients silently clear playback for a direct `uris` request.
    # Starting the album at the requested track works on those clients.
    if album_uri:
        kwargs.update(context_uri=album_uri, offset={"uri": resolved_uri})
    else:
        kwargs["uris"] = [resolved_uri]
    try:
        spotify.start_playback(**kwargs)
    except Exception as error:
        if getattr(error, "http_status", None) == 404:
            raise PlaybackError(
                "A Spotify-eszköz időközben inaktív lett. Indíts el rajta "
                "kézzel egy dalt, majd próbáld újra."
            ) from error
        raise

    for _ in range(5):
        time.sleep(0.4)
        playback = spotify.current_playback() or {}
        item = playback.get("item") or {}
        playing_uris = {item.get("uri"), (item.get("linked_from") or {}).get("uri")}
        if (playback.get("is_playing") and playing_uris & accepted_uris
                and (playback.get("device") or {}).get("id") == device["id"]):
            remaining_ms = max(0, (item.get("duration_ms") or track.get("duration_ms") or 0)
                               - (playback.get("progress_ms") or 0))
            return {
                "device_id": device["id"],
                "album_uri": album_uri,
                "accepted_uris": list(accepted_uris),
                "check_at": time.monotonic() + remaining_ms / 1000,
            }
    raise PlaybackError(
        "A Spotify elfogadta az indítást, de a kért dal nem kezdett el játszódni. "
        "Próbálj kézi lejátszást a Spotifyban, vagy válts a Spotify webes lejátszójára."
    )


def stop_album_continuation(spotify, guard):
    """After the requested song ends, prevent the rest of its album playing.

    Called by the host's existing refresh loop; no polling while the song plays.
    A manually paused or sought song gets a revised check time.
    """
    if not guard or not guard.get("album_uri") or time.monotonic() < guard["check_at"]:
        return guard
    playback = spotify.current_playback() or {}
    if (playback.get("device") or {}).get("id") != guard["device_id"]:
        return None
    item = playback.get("item") or {}
    uris = {item.get("uri"), (item.get("linked_from") or {}).get("uri")}
    if uris & set(guard["accepted_uris"]):
        remaining = max(1, ((item.get("duration_ms") or 0)
                            - (playback.get("progress_ms") or 0)) / 1000)
        return {**guard, "check_at": time.monotonic() + remaining}
    if (playback.get("is_playing")
            and (playback.get("context") or {}).get("uri") == guard["album_uri"]):
        spotify.pause_playback(device_id=guard["device_id"])
    return None
