import csv
import getpass
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException


INPUT_FILE = "hitster_curated_catalog.csv"
OUTPUT_FILE = "songs_with_spotify.csv"

REDIRECT_URI = "http://127.0.0.1:8888/callback"
MARKET = "HU"
SEARCH_LIMIT = 10
SAVE_EVERY = 20
REQUEST_DELAY = 0.18

# Ha egy találat ennél gyengébb, inkább üresen hagyjuk,
# mint hogy rossz Spotify-dalt írjunk a CSV-be.
MIN_SCORE = 78

BAD_TITLE_WORDS = [
    "karaoke",
    "tribute",
    "cover version",
    "instrumental",
    "sped up",
    "slowed",
    "nightcore",
    "workout",
    "fitness",
]

VERSION_PENALTIES = [
    "live",
    "remix",
    "remastered",
    "remaster",
    "re-recorded",
    "rerecorded",
    "acoustic",
    "edit",
]


def normalize(text):
    """Összehasonlításhoz egységesíti a szöveget."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()

    # Gyakori feat./írásjel eltérések.
    text = text.replace("&", " and ")
    text = re.sub(r"\b(feat|featuring|ft)\.?\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)

    return " ".join(text.split())


def normalize_title(text):
    """A dalcím összehasonlításához a verzió-megjelöléseket is tompítja."""
    text = normalize(text)

    removable = [
        "radio edit",
        "single edit",
        "single version",
        "album version",
        "original version",
        "remastered",
        "remaster",
        "re recorded",
        "rerecorded",
    ]

    for phrase in removable:
        text = text.replace(phrase, " ")

    # Évszámos remasterek, pl. "2011 Remaster"
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)

    return " ".join(text.split())


def similarity(a, b):
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).ratio() * 100


def main_artist(artist_text):
    """
    A CSV-ben pl. 'Gotye feat. Kimbra' lehet,
    Spotify-on pedig az előadók külön mezőben vannak.
    A fő előadót külön is használjuk az összehasonlításnál.
    """
    text = re.split(
        r"\s+(?:feat\.?|ft\.?|featuring)\s+|,\s*| & ",
        str(artist_text),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return normalize(text)


def all_spotify_artists(track):
    return normalize(" ".join(
        artist.get("name", "")
        for artist in track.get("artists", [])
    ))


def track_year(track):
    date = (
        track.get("album", {})
        .get("release_date", "")
    )

    match = re.match(r"(\d{4})", str(date))
    return int(match.group(1)) if match else None


def obvious_bad_version(title):
    t = normalize(title)
    return any(normalize(word) in t for word in BAD_TITLE_WORDS)


def candidate_score(row, track):
    wanted_title = normalize_title(row["title"])
    found_title = normalize_title(track.get("name", ""))

    wanted_artist = normalize(row["artist"])
    wanted_main_artist = main_artist(row["artist"])
    found_artists = all_spotify_artists(track)

    title_score = similarity(wanted_title, found_title)

    full_artist_score = similarity(wanted_artist, found_artists)
    main_artist_score = similarity(wanted_main_artist, found_artists)
    artist_score = max(full_artist_score, main_artist_score)

    # A cím a legfontosabb, utána az előadó.
    score = title_score * 0.66 + artist_score * 0.34

    found_year = track_year(track)
    wanted_year = None

    try:
        wanted_year = int(row.get("year", "") or 0)
    except ValueError:
        pass

    if wanted_year and found_year:
        diff = abs(wanted_year - found_year)

        # Spotify remaster/reissue miatt az év nem döntő,
        # csak plusz/mínusz jel.
        if diff == 0:
            score += 6
        elif diff <= 1:
            score += 4
        elif diff <= 3:
            score += 1
        elif diff >= 15:
            score -= 5

    found_name = normalize(track.get("name", ""))

    if obvious_bad_version(track.get("name", "")):
        score -= 35

    for word in VERSION_PENALTIES:
        if normalize(word) in found_name:
            score -= 4

    # Ha a normalizált cím szinte pontos, kapjon kis bónuszt.
    if wanted_title == found_title:
        score += 8

    # Ha a fő előadó neve konkrétan benne van a Spotify előadómezőben.
    if wanted_main_artist and wanted_main_artist in found_artists:
        score += 6

    return score


def safe_search(spotify, query):
    """
    2026-os Development Mode kompatibilis:
    a Spotify Search limit maximuma 10.
    """
    while True:
        try:
            result = spotify.search(
                q=query,
                type="track",
                market=MARKET,
                limit=SEARCH_LIMIT,
            )
            time.sleep(REQUEST_DELAY)
            return result.get("tracks", {}).get("items", [])

        except SpotifyException as exc:
            # 429 esetén tiszteletben tartjuk a Retry-After fejlécet.
            if exc.http_status == 429:
                retry_after = 2

                headers = getattr(exc, "headers", None) or {}
                try:
                    retry_after = int(headers.get("Retry-After", retry_after))
                except (TypeError, ValueError):
                    retry_after = 2

                retry_after = max(1, retry_after)
                print(f"  Spotify rate limit: várakozás {retry_after} mp...")
                time.sleep(retry_after + 0.5)
                continue

            raise


def search_track(spotify, row):
    artist = row["artist"].strip()
    title = row["title"].strip()

    queries = [
        f'track:"{title}" artist:"{artist}"',
        f'"{title}" "{artist}"',
        f'{title} {artist}',
    ]

    all_candidates = []
    seen_uri = set()

    for query in queries:
        try:
            tracks = safe_search(spotify, query)
        except SpotifyException as exc:
            print(
                f"  Keresési hiba ({exc.http_status}) ennél: "
                f"{artist} – {title}"
            )
            continue

        for track in tracks:
            uri = track.get("uri")
            if not uri or uri in seen_uri:
                continue

            seen_uri.add(uri)
            all_candidates.append(track)

        # Ha már van nagyon erős találat, nem kell még több API-hívás.
        if all_candidates:
            best_now = max(
                candidate_score(row, track)
                for track in all_candidates
            )
            if best_now >= 97:
                break

    if not all_candidates:
        return None, None

    scored = sorted(
        (
            (candidate_score(row, track), track)
            for track in all_candidates
        ),
        key=lambda x: x[0],
        reverse=True,
    )

    best_score, best_track = scored[0]

    if best_score < MIN_SCORE:
        return None, best_score

    return best_track, best_score


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save_rows(path, rows, fieldnames):
    temp_path = str(path) + ".tmp"

    with open(
        temp_path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    Path(temp_path).replace(path)


def build_spotify():
    client_id = input("Spotify Client ID: ").strip()
    client_secret = getpass.getpass(
        "Spotify Client Secret (nem fog látszani): "
    ).strip()
    refresh_token = getpass.getpass(
        "Spotify Refresh Token (nem fog látszani): "
    ).strip()

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope="user-read-playback-state user-modify-playback-state",
        open_browser=False,
        cache_path=None,
    )

    # Nem indítunk új OAuth-login folyamatot.
    # A már megszerzett refresh tokenből kérünk access tokent.
    token_info = auth_manager.refresh_access_token(refresh_token)

    return spotipy.Spotify(
        auth=token_info["access_token"],
        requests_timeout=20,
        retries=3,
    )


def main():
    input_path = Path(INPUT_FILE)
    output_path = Path(OUTPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Nem találom ezt a fájlt: {INPUT_FILE}\n"
            "Tedd a script mellé a repo gyökerébe."
        )

    rows = load_rows(input_path)

    if not rows:
        raise RuntimeError("A CSV üres.")

    required = {"artist", "title", "year"}
    missing = required - set(rows[0].keys())

    if missing:
        raise RuntimeError(
            "Hiányzó oszlop(ok): " + ", ".join(sorted(missing))
        )

    # Megtartjuk az összes meglévő oszlopot.
    fieldnames = list(rows[0].keys())

    if "spotify_uri" not in fieldnames:
        fieldnames.append("spotify_uri")
        for row in rows:
            row["spotify_uri"] = ""

    # Hasznos ellenőrző mezők.
    extra_fields = [
        "spotify_match_score",
        "spotify_match_artist",
        "spotify_match_title",
        "spotify_album_year",
        "spotify_match_status",
    ]

    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    # Ha egy korábbi futás félbeszakadt, a meglévő outputból folytatjuk.
    if output_path.exists():
        previous = load_rows(output_path)

        if len(previous) == len(rows):
            rows = previous
            fieldnames = list(rows[0].keys())
            print(
                f"Korábbi eredmény betöltve: {OUTPUT_FILE} "
                f"({len(rows)} sor)"
            )
        else:
            print(
                "A meglévő output sorszáma eltér az inputétól, "
                "ezért újra az inputból indulok."
            )

    spotify = build_spotify()

    total = len(rows)
    already_done = sum(
        1
        for row in rows
        if row.get("spotify_match_status") in {"ok", "not_found"}
    )

    print()
    print(f"Dalok összesen: {total}")
    print(f"Már feldolgozva: {already_done}")
    print()

    found = 0
    not_found = 0
    processed_this_run = 0

    for index, row in enumerate(rows, start=1):
        status = row.get("spotify_match_status", "").strip()

        # Resume: kész sorokat nem keresünk újra.
        if status in {"ok", "not_found"}:
            continue

        artist = row["artist"].strip()
        title = row["title"].strip()

        print(f"[{index}/{total}] {artist} – {title}")

        try:
            track, score = search_track(spotify, row)
        except Exception as exc:
            print(f"  HIBA: {exc}")
            row["spotify_match_status"] = "error"
            processed_this_run += 1

            if processed_this_run % SAVE_EVERY == 0:
                save_rows(output_path, rows, fieldnames)
                print("  Részmentés kész.")

            continue

        if track:
            row["spotify_uri"] = track.get("uri", "")
            row["spotify_match_score"] = f"{score:.1f}"
            row["spotify_match_artist"] = ", ".join(
                a.get("name", "")
                for a in track.get("artists", [])
            )
            row["spotify_match_title"] = track.get("name", "")
            row["spotify_album_year"] = str(track_year(track) or "")
            row["spotify_match_status"] = "ok"

            print(
                f"  OK {score:.1f}: "
                f"{row['spotify_match_artist']} – "
                f"{row['spotify_match_title']}"
            )
            found += 1

        else:
            row["spotify_uri"] = ""
            row["spotify_match_score"] = (
                f"{score:.1f}" if score is not None else ""
            )
            row["spotify_match_artist"] = ""
            row["spotify_match_title"] = ""
            row["spotify_album_year"] = ""
            row["spotify_match_status"] = "not_found"

            print(
                "  NINCS ELÉG BIZTOS TALÁLAT"
                + (
                    f" (legjobb pontszám: {score:.1f})"
                    if score is not None
                    else ""
                )
            )
            not_found += 1

        processed_this_run += 1

        if processed_this_run % SAVE_EVERY == 0:
            save_rows(output_path, rows, fieldnames)
            print("  Részmentés kész.")

    save_rows(output_path, rows, fieldnames)

    total_ok = sum(
        row.get("spotify_match_status") == "ok"
        for row in rows
    )
    total_missing = sum(
        row.get("spotify_match_status") == "not_found"
        for row in rows
    )
    total_error = sum(
        row.get("spotify_match_status") == "error"
        for row in rows
    )

    low_confidence = sum(
        1
        for row in rows
        if row.get("spotify_match_status") == "ok"
        and row.get("spotify_match_score")
        and float(row["spotify_match_score"]) < 90
    )

    print()
    print("==============================")
    print("KÉSZ")
    print("==============================")
    print(f"Dalok összesen: {total}")
    print(f"Spotify URI megtalálva: {total_ok}")
    print(f"Nem talált: {total_missing}")
    print(f"Hibával maradt: {total_error}")
    print(f"90 pont alatti találat: {low_confidence}")
    print(f"Fájl: {OUTPUT_FILE}")
    print()
    print(
        "A 90 pont alatti találatokat érdemes majd külön "
        "átellenőriznünk, mielőtt songs.csv lesz belőle."
    )


if __name__ == "__main__":
    main()
