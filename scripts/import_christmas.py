"""Resolve the Christmas shortlist on Spotify, then merge confirmed matches.

Run from the repository root:
    .venv/bin/python scripts/import_christmas.py --resolve
    .venv/bin/python scripts/import_christmas.py --merge
Credentials are read locally; no tokens or secrets are written to the reports.
"""

import argparse
import csv
import logging
from pathlib import Path
import re
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolve_curated_spotify import normalize, normalize_title, similarity
from resolve_curated_spotify_v2 import main_artist

SOURCE = ROOT / "christmas_catalog.csv"
RESULT = ROOT / "reports/christmas_spotify_matches.csv"
CATALOG = ROOT / "songs.csv"
MATCH_FIELDS = ["spotify_match_status", "spotify_match_artist", "spotify_match_title",
                "spotify_album_year", "spotify_title_score", "spotify_artist_score"]
ARTIST_ALIASES = {"EDDA Művek": "Edda", "Halász Judit": "Judit Halasz"}
CHRISTMAS = "Karácsonyi slágerek"


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader), list(reader.fieldnames)


def save_rows(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def identity(row):
    return normalize(row["artist"]), matching_title(row["title"])


def matching_title(title):
    # A numeric song title (e.g. "1979") is not a remaster's year suffix.
    base = re.split(
        r"\s*(?:-\s*|\()\s*(?:\d{4}\s+)?remaster(?:ed)?\b",
        title, maxsplit=1, flags=re.I,
    )[0]
    return normalize_title(base) or normalize(base)


def candidate_scores(row, track):
    # A credited guest is metadata, not a different song title.
    candidate_title = re.sub(r"\s*[([]?(?:feat\.?|featuring)\s+.*", "", track["name"], flags=re.I)
    candidate_title = re.sub(r"\s*-\s*(?:mono|stereo)(?: version| mix)?\s*$", "", candidate_title, flags=re.I)
    candidate_title = re.sub(r'\s*-\s*From ["“].* Soundtrack\s*$', "", candidate_title, flags=re.I)
    title = matching_title(candidate_title)
    wanted_title = matching_title(row["title"])
    wanted_artists = {normalize(main_artist(row["artist"])),
                      normalize(ARTIST_ALIASES.get(row["artist"], main_artist(row["artist"])))}
    if row["artist"] == "Bojtorján":
        wanted_artists.add(normalize("Bojtorjan Ensemble"))
    artist_score = max((similarity(wanted, normalize(a["name"]))
                        for a in track.get("artists", []) for wanted in wanted_artists), default=0)
    title_score = similarity(wanted_title, title)
    for word in ["karaoke", "tribute", "sped up", "slowed", "nightcore", "live", "remix", "acoustic", "rehearsal", "demo"]:
        if word in title.split() and word not in wanted_title.split():
            return 0, 0
    if "instrumental" in title and "instrumental" not in wanted_title:
        return 0, 0
    return title_score, artist_score


def resolve():
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    logging.getLogger("spotipy").setLevel(logging.CRITICAL)
    settings = tomllib.loads((ROOT / ".streamlit/secrets.toml").read_text())
    oauth = SpotifyOAuth(
        client_id=settings["SPOTIFY_CLIENT_ID"],
        client_secret=settings["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=settings.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        cache_handler=spotipy.cache_handler.MemoryCacheHandler(),
        open_browser=False, requests_timeout=15,
    )
    token = oauth.refresh_access_token(settings["SPOTIFY_REFRESH_TOKEN"])
    spotify = spotipy.Spotify(auth=token["access_token"], requests_timeout=15, retries=0)
    rows, fields = read_rows(SOURCE)
    fields += MATCH_FIELDS
    saved = {identity(row): row for row in read_rows(RESULT)[0]} if RESULT.exists() else {}
    existing = {identity(row): row for row in read_rows(CATALOG)[0]}
    for row in rows:
        previous = saved.get(identity(row), {})
        for field in ["spotify_uri", *MATCH_FIELDS]:
            row[field] = previous.get(field, row.get(field, ""))
    for index, row in enumerate(rows, 1):
        if row["spotify_uri"] and row["spotify_match_status"] == "ok":
            continue
        previous = existing.get(identity(row))
        if previous and re.fullmatch(r"spotify:track:[A-Za-z0-9]{22}", previous["spotify_uri"]):
            row.update(spotify_uri=previous["spotify_uri"], spotify_match_status="ok",
                       spotify_match_artist=previous["artist"], spotify_match_title=previous["title"],
                       spotify_title_score=100, spotify_artist_score=100)
        else:
            artist = ARTIST_ALIASES.get(row["artist"], main_artist(row["artist"]))
            queries = [f'track:"{row["title"]}" artist:"{artist}"', f'{artist} {row["title"]}']
            candidates = []
            try:
                for query in queries:
                    response = spotify.search(q=query, type="track", market="HU", limit=10)
                    candidates += response.get("tracks", {}).get("items", [])
                    strong = [t for t in candidates if all(s >= 85 for s in candidate_scores(row, t))]
                    if strong:
                        break
                    time.sleep(0.5)
            except Exception as error:
                status = getattr(error, "http_status", None)
                row["spotify_match_status"] = f"error_{status or type(error).__name__}"
                save_rows(RESULT, rows, fields)
                print(f"Stopped at {index}: {type(error).__name__}, HTTP {status}", flush=True)
                if status == 429:
                    print("Retry-After:", (getattr(error, "headers", {}) or {}).get("Retry-After", "unknown"), flush=True)
                return False
            ranked = sorted(candidates, key=lambda t: sum(candidate_scores(row, t)), reverse=True)
            best = ranked[0] if ranked else None
            title_score, artist_score = candidate_scores(row, best) if best else (0, 0)
            if best:
                row.update(spotify_match_artist=", ".join(a["name"] for a in best["artists"]),
                           spotify_match_title=best["name"],
                           spotify_album_year=best.get("album", {}).get("release_date", "")[:4],
                           spotify_title_score=round(title_score, 1), spotify_artist_score=round(artist_score, 1))
            if best and title_score >= 85 and artist_score >= 85 and best.get("is_playable", True):
                row.update(spotify_uri=best["uri"], spotify_match_status="ok")
            else:
                row["spotify_match_status"] = "needs_review" if best else "not_found"
        save_rows(RESULT, rows, fields)
        print(f'{index}/{len(rows)} {row["spotify_match_status"]}: {row["artist"]} – {row["title"]}', flush=True)
        time.sleep(0.5)
    save_rows(RESULT, rows, fields)
    return True


def merge(expected_count=150, tag=CHRISTMAS):
    source, _ = read_rows(SOURCE)
    matches, _ = read_rows(RESULT)
    matched = {identity(row): row for row in matches}
    if len(source) != expected_count or len({identity(row) for row in source}) != expected_count:
        raise ValueError(f"The shortlist must contain {expected_count} distinct artist/title pairs.")
    verified = []
    for row in source:
        match = matched.get(identity(row), {})
        if match.get("spotify_match_status") != "ok" or not re.fullmatch(r"spotify:track:[A-Za-z0-9]{22}", match.get("spotify_uri", "")):
            raise ValueError(f'Unresolved recording: {row["artist"]} – {row["title"]}')
        if row["difficulty"] not in {"1", "2", "3"} or row["language"] not in {"hu", "international"}:
            raise ValueError("Invalid difficulty or language")
        if not 1950 <= int(row["year"]) <= 2029:
            raise ValueError("Year outside the app's supported decades")
        verified.append({**row, "spotify_uri": match["spotify_uri"]})
    if len({r["spotify_uri"] for r in verified}) != expected_count:
        raise ValueError("The shortlist contains duplicate Spotify recordings.")
    rows, fields = read_rows(CATALOG)
    old_count = len(rows)
    by_identity = {identity(row): row for row in rows}
    by_uri = {row["spotify_uri"]: row for row in rows}
    tagged = added = 0
    for song in verified:
        existing = by_uri.get(song["spotify_uri"]) or by_identity.get(identity(song))
        if existing:
            tags = [tag.strip() for tag in existing["style"].split("/")]
            if tag not in tags:
                existing["style"] += " / " + tag
            tagged += 1
        else:
            item = {field: song.get(field, "") for field in fields}
            rows.append(item)
            by_uri[song["spotify_uri"]] = item
            by_identity[identity(song)] = item
            added += 1
    assert len(rows) == old_count + added
    save_rows(CATALOG, rows, fields)
    print(f"Added: {added}; tagged existing: {tagged}; total: {len(rows)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    if not args.resolve and not args.merge:
        parser.error("Choose --resolve or --merge")
    if args.resolve and not resolve():
        raise SystemExit(1)
    if args.merge:
        merge()
