import csv
import getpass
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

INPUT_FILE = "songs_with_spotify.csv"
CATALOG_FILE = "hitster_curated_catalog.csv"
OUTPUT_FILE = "songs_with_spotify.csv"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
MARKET = "HU"
SEARCH_LIMIT = 10
REQUEST_DELAY = 0.35
SAVE_EVERY = 10
MIN_SCORE = 78

PRIORITY_DECADES = {
    "2020s": 0, "2010s": 1, "2000s": 2, "1990s": 3,
    "1980s": 4, "1970s": 5, "1960s": 6, "1950s": 7,
}

OUTPUT_COLUMNS = [
    "artist", "title", "year", "decade", "style", "language",
    "spotify_uri", "year_needs_review", "spotify_match_score",
    "spotify_match_artist", "spotify_match_title", "spotify_album_year",
    "spotify_match_status",
]

def clean(v):
    return "" if v is None else str(v).strip()

def normalize(v):
    v = unicodedata.normalize("NFKD", clean(v))
    v = "".join(c for c in v if not unicodedata.combining(c)).lower()
    v = re.sub(r"\b(feat|featuring|ft)\.?\b.*$", "", v)
    v = re.sub(r"[^a-z0-9]+", " ", v)
    return re.sub(r"\s+", " ", v).strip()

def similarity(a, b):
    a, b = normalize(a), normalize(b)
    return SequenceMatcher(None, a, b).ratio() * 100 if a and b else 0

def main_artist(artist):
    artist = clean(artist)
    lower = artist.lower()
    for sep in [" feat.", " feat ", " ft.", " ft ", " featuring ", ",", " & "]:
        pos = lower.find(sep)
        if pos >= 0:
            return artist[:pos].strip()
    return artist

def album_year(track):
    date = clean((track.get("album") or {}).get("release_date"))
    return int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else ""

def score_candidate(row, track):
    wanted_title = clean(row["title"])
    wanted_artist = clean(row["artist"])
    got_title = clean(track.get("name"))
    got_artists = ", ".join(a.get("name", "") for a in track.get("artists", []))

    score = similarity(wanted_title, got_title) * 0.68 + similarity(wanted_artist, got_artists) * 0.32
    wt, gt = normalize(wanted_title), normalize(got_title)
    wa, ga = normalize(main_artist(wanted_artist)), normalize(got_artists)

    if wt == gt:
        score += 10
    if wa and wa in ga:
        score += 6

    for word in ["karaoke", "tribute", "instrumental", "sped up", "slowed", "nightcore", "workout", "fitness"]:
        if word in gt:
            score -= 35
    for word in ["live", "remix", "re recorded", "rerecorded", "acoustic", "radio edit"]:
        if word in gt and word not in wt:
            score -= 12

    sy = album_year(track)
    if sy:
        diff = abs(sy - int(row["year"]))
        if diff == 0:
            score += 4
        elif diff <= 2:
            score += 2
        elif diff >= 15:
            score -= 3
    return round(score, 1)

def search_once(sp, row):
    q = f'track:"{clean(row["title"])}" artist:"{main_artist(row["artist"])}"'
    result = sp.search(q=q, type="track", market=MARKET, limit=SEARCH_LIMIT)
    items = result.get("tracks", {}).get("items", [])
    if not items:
        return None, 0
    scored = sorted(((score_candidate(row, t), t) for t in items), key=lambda x: x[0], reverse=True)
    return scored[0][1], scored[0][0]

def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def save_rows(rows):
    tmp = Path(OUTPUT_FILE + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in OUTPUT_COLUMNS})
    tmp.replace(OUTPUT_FILE)

def load_rows():
    if Path(INPUT_FILE).exists():
        rows = load_csv(INPUT_FILE)
        print(f"Meglévő eredmény betöltve: {len(rows)} dal")
    elif Path(CATALOG_FILE).exists():
        rows = load_csv(CATALOG_FILE)
        print(f"Katalógus betöltve: {len(rows)} dal")
    else:
        raise FileNotFoundError(f"Nem találom: {INPUT_FILE} vagy {CATALOG_FILE}")
    for row in rows:
        for c in OUTPUT_COLUMNS:
            row.setdefault(c, "")
    return rows

def priority(row):
    lang = clean(row.get("language")).lower()
    return (0 if lang == "hu" else 1, PRIORITY_DECADES.get(clean(row.get("decade")), 99))

def make_client(client_id, client_secret, refresh_token):
    oauth = SpotifyOAuth(
        client_id=client_id, client_secret=client_secret,
        redirect_uri=REDIRECT_URI, scope="", cache_path=None,
        open_browser=False, requests_timeout=15,
    )
    token = oauth.refresh_access_token(refresh_token)
    return spotipy.Spotify(auth=token["access_token"], requests_timeout=15, retries=0)

def main():
    print("Spotify resolver – takarékos folytatás")
    client_id = input("Spotify Client ID: ").strip()
    client_secret = getpass.getpass("Spotify Client Secret: ").strip()
    refresh_token = getpass.getpass("Spotify Refresh Token: ").strip()
    sp = make_client(client_id, client_secret, refresh_token)
    rows = load_rows()

    pending = [
        i for i, row in enumerate(rows)
        if not clean(row.get("spotify_uri"))
        and clean(row.get("spotify_match_status")).lower() not in {"ok", "not_found"}
    ]
    pending.sort(key=lambda i: priority(rows[i]))

    print(f"Már URI-val rendelkező dalok: {sum(bool(clean(r.get('spotify_uri'))) for r in rows)}")
    print(f"Még feldolgozandó: {len(pending)}")
    print("Sorrend: magyar dalok először, azon belül 2020s → 1950s; utána nemzetközi ugyanígy.")

    processed = found = missed = 0

    for n, idx in enumerate(pending, 1):
        row = rows[idx]
        print(f"[{n}/{len(pending)}] {row['artist']} – {row['title']} ({row['year']})")

        try:
            track, score = search_once(sp, row)
        except SpotifyException as exc:
            status = getattr(exc, "http_status", None)

            if status == 401:
                print("  Access token frissítése...")
                try:
                    sp = make_client(client_id, client_secret, refresh_token)
                    track, score = search_once(sp, row)
                except SpotifyException as exc2:
                    exc, status = exc2, getattr(exc2, "http_status", None)
                else:
                    status = None

            if status == 429:
                save_rows(rows)
                headers = getattr(exc, "headers", {}) or {}
                retry_after = headers.get("Retry-After")
                text = (str(getattr(exc, "msg", "")) + " " + str(exc)).upper()
                print("\nSpotify 429: a futás leállt, az eredmény elmentve.")
                if "QUOTA_EXCEEDED" in text:
                    print("Ok: Development Mode QUOTA_EXCEEDED.")
                if retry_after:
                    print(f"Retry-After: {retry_after} másodperc.")
                print(f"Mentett fájl: {OUTPUT_FILE}")
                print("Később ugyanígy indítsd újra; a kész sorokat kihagyja.")
                return

            if status is not None:
                row["spotify_match_status"] = "error"
                print(f"  Spotify hiba: {status} – {exc}")
                save_rows(rows)
                continue

        except Exception as exc:
            row["spotify_match_status"] = "error"
            print(f"  Hiba: {exc}")
            save_rows(rows)
            continue

        processed += 1

        if track and score >= MIN_SCORE:
            row["spotify_uri"] = clean(track.get("uri"))
            row["spotify_match_score"] = score
            row["spotify_match_artist"] = ", ".join(a.get("name", "") for a in track.get("artists", []))
            row["spotify_match_title"] = clean(track.get("name"))
            row["spotify_album_year"] = album_year(track)
            row["spotify_match_status"] = "ok"
            found += 1
            print(f"  OK ({score}): {row['spotify_match_artist']} – {row['spotify_match_title']}")
        else:
            row["spotify_match_score"] = score or ""
            row["spotify_match_status"] = "not_found"
            missed += 1
            print(f"  Nem elég biztos találat (score: {score}).")

        if processed % SAVE_EVERY == 0:
            save_rows(rows)
            print("  Mentve.")

        time.sleep(REQUEST_DELAY)

    save_rows(rows)
    print("\nKÉSZ")
    print(f"Most feldolgozva: {processed}")
    print(f"Most megtalálva: {found}")
    print(f"Most nem talált: {missed}")
    print(f"Spotify URI összesen: {sum(bool(clean(r.get('spotify_uri'))) for r in rows)}")
    print(f"Fájl: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
