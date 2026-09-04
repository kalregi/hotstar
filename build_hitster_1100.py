import csv
import re
import time
import unicodedata
from collections import Counter
from getpass import getpass
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth


# ============================================================
# BEÁLLÍTÁSOK
# ============================================================

BASE_FILES = [
    "songs.csv",
    "hitster_133_corrected_source.csv",
    "hitster_120_source.csv",
]

PLAN_FILE = "hitster_catalog_plan.csv"
OUTPUT_FILE = "songs_expanded.csv"

# Kb. ennyi dal legyen összesen a végén.
TARGET_TOTAL = 1100

MARKET = "HU"

BAD_WORDS = [
    "karaoke",
    "tribute",
    "cover version",
    "instrumental version",
    "sped up",
    "slowed",
    "nightcore",
    "workout mix",
    "fitness version",
]

SOFT_BAD_WORDS = [
    "live",
    "remix",
    "remastered",
    "remaster",
    "re-recorded",
    "rerecorded",
    "edit",
]

HUNGARIAN_ARTISTS = [
    "Omega",
    "Illés",
    "Koncz Zsuzsa",
    "Zalatnay Sarolta",
    "Locomotiv GT",
    "Presser Gábor",
    "Zorán",
    "Máté Péter",
    "Szécsi Pál",
    "Korda György",
    "Neoton Família",
    "Hungária",
    "KFT",
    "EDDA Művek",
    "Bikini",
    "Beatrice",
    "Demjén Ferenc",
    "R-GO",
    "Zoltán Erika",
    "Bonanza Banzai",
    "Ákos",
    "Pa-Dö-Dö",
    "Republic",
    "Zámbó Jimmy",
    "Ámokfutók",
    "Emergency House",
    "Carpe Diem",
    "TNT",
    "Soho Party",
    "Tankcsapda",
    "United",
    "Groovehouse",
    "NOX",
    "Hooligans",
    "Quimby",
    "Magna Cum Laude",
    "Fluor",
    "Punnany Massif",
    "Majka",
    "Curtis",
    "Wellhello",
    "Halott Pénz",
    "Bagossy Brothers Company",
    "Azahriah",
    "DESH",
    "Follow The Flow",
    "Rúzsa Magdolna",
    "ByeAlex és a Slepp",
    "Kelemen Kabátban",
    "Konyha",
    "Napoleon Boulevard",
    "Pokolgép",
    "Ossian",
    "Hip Hop Boyz",
    "V-Tech",
    "Crystal",
    "Fiesta",
    "Caramel",
    "Krisz Rudolf",
    "Oláh Ibolya",
    "VALMAR",
]


# ============================================================
# SEGÉDFÜGGVÉNYEK
# ============================================================

def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(
        ch for ch in text
        if not unicodedata.combining(ch)
    )
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(
        r"\b(remaster(?:ed)?|radio edit|single version|album version)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def song_key(artist, title):
    main_artist = re.split(
        r"\s*(?:feat\.?|ft\.?|&|,)\s*",
        artist or "",
        maxsplit=1,
        flags=re.I,
    )[0]

    return (
        normalize(main_artist),
        normalize(title),
    )


def get_decade(year):
    year = int(year)

    if year < 1950:
        return "pre-1950"

    return f"{(year // 10) * 10}s"


def has_bad_word(title):
    text = (title or "").lower()
    return any(word in text for word in BAD_WORDS)


def soft_penalty(title):
    text = (title or "").lower()
    return sum(
        1 for word in SOFT_BAD_WORDS
        if word in text
    )


def track_year(track):
    release_date = (
        track.get("album", {})
        .get("release_date", "")
    )

    if not release_date:
        return None

    try:
        return int(release_date[:4])
    except ValueError:
        return None


def compact_artists(track):
    return ", ".join(
        artist["name"]
        for artist in track.get("artists", [])
    )


def find_base_file():
    for filename in BASE_FILES:
        if Path(filename).exists():
            return filename

    return None


def read_base_rows():
    filename = find_base_file()

    if filename is None:
        print(
            "Nem találtam régi dalfájlt. "
            "Nulláról építem a katalógust."
        )
        return []

    print(f"Alaplista: {filename}")

    rows = []

    with open(
        filename,
        encoding="utf-8-sig",
    ) as f:
        for row in csv.DictReader(f):
            artist = row.get("artist", "").strip()
            title = row.get("title", "").strip()

            if not artist or not title:
                continue

            try:
                year = int(row.get("year", ""))
            except ValueError:
                continue

            rows.append(
                {
                    "artist": artist,
                    "title": title,
                    "year": year,
                    "decade": row.get(
                        "decade",
                        get_decade(year),
                    ),
                    "style": row.get(
                        "style",
                        "Curated",
                    ),
                    "language": row.get(
                        "language",
                        "hu"
                        if any(
                            normalize(a)
                            in normalize(artist)
                            for a in HUNGARIAN_ARTISTS
                        )
                        else "international",
                    ),
                    "spotify_uri": row.get(
                        "spotify_uri",
                        "",
                    ).strip(),
                    "spotify_popularity": row.get(
                        "spotify_popularity",
                        "",
                    ),
                    "year_source": row.get(
                        "year_source",
                        "curated",
                    ),
                    "needs_year_review": row.get(
                        "needs_year_review",
                        "no",
                    ),
                }
            )

    print(
        f"Alaplistából betöltve: {len(rows)} dal"
    )

    return rows


def read_plan():
    with open(
        PLAN_FILE,
        encoding="utf-8-sig",
    ) as f:
        return list(csv.DictReader(f))


def authenticate():
    client_id = input(
        "Spotify Client ID: "
    ).strip()

    client_secret = getpass(
        "Spotify Client Secret "
        "(nem fog látszani): "
    ).strip()

    refresh_token = getpass(
        "Spotify Refresh Token "
        "(nem fog látszani): "
    ).strip()

    oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=(
            "http://127.0.0.1:8888/callback"
        ),
        scope=(
            "user-read-playback-state "
            "user-modify-playback-state"
        ),
        cache_path=None,
        open_browser=False,
    )

    token_info = oauth.refresh_access_token(
        refresh_token
    )

    return spotipy.Spotify(
        auth=token_info["access_token"],
        requests_timeout=20,
        retries=3,
    )


def search_best_track(
    spotify,
    artist,
    title,
):
    queries = [
        f'track:"{title}" artist:"{artist}"',
        f"{artist} {title}",
    ]

    candidates = []

    for query in queries:
        try:
            result = spotify.search(
                q=query,
                type="track",
                limit=10,
                market=MARKET,
            )
        except Exception:
            continue

        candidates.extend(
            result["tracks"]["items"]
        )

    if not candidates:
        return None

    target_artist = normalize(artist)
    target_title = normalize(title)

    scored = []

    for track in candidates:
        if has_bad_word(track["name"]):
            continue

        track_artists = " ".join(
            normalize(a["name"])
            for a in track["artists"]
        )

        track_title = normalize(
            track["name"]
        )

        score = 0

        if target_title == track_title:
            score += 100
        elif (
            target_title in track_title
            or track_title in target_title
        ):
            score += 65

        if target_artist in track_artists:
            score += 80

        score += min(
            int(track.get("popularity", 0)),
            100,
        ) * 0.15

        score -= soft_penalty(
            track["name"]
        ) * 12

        scored.append(
            (score, track)
        )

    if not scored:
        return None

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return scored[0][1]


def resolve_base_rows(
    spotify,
    rows,
):
    result = []

    for index, row in enumerate(
        rows,
        start=1,
    ):
        if row.get("spotify_uri"):
            result.append(row)
            continue

        track = search_best_track(
            spotify,
            row["artist"],
            row["title"],
        )

        if track:
            row["spotify_uri"] = track["uri"]
            row["spotify_popularity"] = (
                track.get("popularity", "")
            )

            print(
                f"[alap {index}/{len(rows)}] "
                f"OK: {row['artist']} – "
                f"{row['title']}"
            )
        else:
            print(
                f"[alap {index}/{len(rows)}] "
                f"NINCS: {row['artist']} – "
                f"{row['title']}"
            )

        result.append(row)

        time.sleep(0.05)

    return result


def fetch_bucket_tracks(
    spotify,
    start_year,
    end_year,
    genre_query,
    wanted,
    known_keys,
):
    query = (
        f"year:{start_year}-{end_year} "
        f'genre:"{genre_query}"'
    )

    pool = []

    # Több oldalt nézünk meg, majd népszerűség
    # alapján választunk közülük.
    for offset in range(0, 400, 50):
        try:
            result = spotify.search(
                q=query,
                type="track",
                limit=50,
                offset=offset,
                market=MARKET,
            )
        except Exception as e:
            print(
                f"Spotify keresési hiba: {e}"
            )
            break

        items = result["tracks"]["items"]

        if not items:
            break

        for track in items:
            title = track["name"]

            if has_bad_word(title):
                continue

            year = track_year(track)

            if year is None:
                continue

            if not (
                start_year
                <= year
                <= end_year
            ):
                continue

            duration = track.get(
                "duration_ms",
                0,
            )

            if duration < 90000:
                continue

            if duration > 8 * 60 * 1000:
                continue

            artist = compact_artists(
                track
            )

            key = song_key(
                artist,
                title,
            )

            if key in known_keys:
                continue

            popularity = int(
                track.get(
                    "popularity",
                    0,
                )
            )

            # Remaster/live/edit maradhat, ha egyébként
            # nagyon ismert, de kapjon hátrányt.
            ranking_score = (
                popularity
                - soft_penalty(title) * 12
            )

            pool.append(
                (
                    ranking_score,
                    popularity,
                    track,
                )
            )

        if len(pool) >= wanted * 5:
            break

        time.sleep(0.05)

    pool.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    selected = []

    for _, _, track in pool:
        artist = compact_artists(track)
        title = track["name"]
        key = song_key(
            artist,
            title,
        )

        if key in known_keys:
            continue

        known_keys.add(key)
        selected.append(track)

        if len(selected) >= wanted:
            break

    return selected


def artist_search(
    spotify,
    artist_name,
):
    result = spotify.search(
        q=f'artist:"{artist_name}"',
        type="artist",
        limit=5,
        market=MARKET,
    )

    items = result["artists"]["items"]

    if not items:
        return None

    target = normalize(artist_name)

    exact = [
        item for item in items
        if normalize(item["name"]) == target
    ]

    if exact:
        return exact[0]

    return items[0]


def add_hungarian_tracks(
    spotify,
    rows,
    known_keys,
    target_new=170,
):
    added = 0

    for artist_name in HUNGARIAN_ARTISTS:
        if added >= target_new:
            break

        try:
            artist = artist_search(
                spotify,
                artist_name,
            )

            if not artist:
                continue

            top = spotify.artist_top_tracks(
                artist["id"],
                country=MARKET,
            )["tracks"]

        except Exception as e:
            print(
                f"Magyar előadó hiba "
                f"({artist_name}): {e}"
            )
            continue

        # Előadónként legfeljebb 4 új dal.
        artist_added = 0

        top = sorted(
            top,
            key=lambda t: t.get(
                "popularity",
                0,
            ),
            reverse=True,
        )

        for track in top:
            if artist_added >= 4:
                break

            title = track["name"]

            if has_bad_word(title):
                continue

            year = track_year(track)

            if year is None:
                continue

            artist_text = compact_artists(
                track
            )

            key = song_key(
                artist_text,
                title,
            )

            if key in known_keys:
                continue

            known_keys.add(key)

            style = "Magyar"

            rows.append(
                {
                    "artist": artist_text,
                    "title": title,
                    "year": year,
                    "decade": get_decade(year),
                    "style": style,
                    "language": "hu",
                    "spotify_uri": track["uri"],
                    "spotify_popularity": (
                        track.get(
                            "popularity",
                            "",
                        )
                    ),
                    "year_source": "spotify",
                    "needs_year_review": (
                        "yes"
                        if soft_penalty(title)
                        else "no"
                    ),
                }
            )

            added += 1
            artist_added += 1

        print(
            f"Magyar: {artist_name} "
            f"(összes új: {added})"
        )

        time.sleep(0.05)

    return added


def add_international_tracks(
    spotify,
    rows,
    known_keys,
    plan,
):
    for plan_row in plan:
        if len(rows) >= TARGET_TOTAL:
            break

        decade = plan_row["decade"]
        style = plan_row["style"]
        wanted = int(
            plan_row["target_count"]
        )

        start_year = int(
            decade[:4]
        )
        end_year = min(
            start_year + 9,
            2026,
        )

        genre_query = (
            plan_row[
                "spotify_genre_query"
            ]
        )

        remaining_slots = (
            TARGET_TOTAL - len(rows)
        )

        wanted = min(
            wanted,
            remaining_slots,
        )

        if wanted <= 0:
            break

        tracks = fetch_bucket_tracks(
            spotify=spotify,
            start_year=start_year,
            end_year=end_year,
            genre_query=genre_query,
            wanted=wanted,
            known_keys=known_keys,
        )

        for track in tracks:
            year = track_year(track)

            rows.append(
                {
                    "artist": compact_artists(
                        track
                    ),
                    "title": track["name"],
                    "year": year,
                    "decade": get_decade(year),
                    "style": style,
                    "language": "international",
                    "spotify_uri": track["uri"],
                    "spotify_popularity": (
                        track.get(
                            "popularity",
                            "",
                        )
                    ),
                    "year_source": "spotify",
                    "needs_year_review": (
                        "yes"
                        if soft_penalty(
                            track["name"]
                        )
                        else "no"
                    ),
                }
            )

        print(
            f"{decade} / {style}: "
            f"+{len(tracks)} "
            f"(összesen {len(rows)})"
        )

        time.sleep(0.05)


def broad_fill(
    spotify,
    rows,
    known_keys,
):
    decade_ranges = [
        (1950, 1959),
        (1960, 1969),
        (1970, 1979),
        (1980, 1989),
        (1990, 1999),
        (2000, 2009),
        (2010, 2019),
        (2020, 2026),
    ]

    round_index = 0

    while len(rows) < TARGET_TOTAL:
        start_year, end_year = (
            decade_ranges[
                round_index
                % len(decade_ranges)
            ]
        )

        query = (
            f"year:{start_year}-{end_year}"
        )

        offset = (
            (
                round_index
                // len(decade_ranges)
            )
            * 50
        ) % 500

        try:
            result = spotify.search(
                q=query,
                type="track",
                limit=50,
                offset=offset,
                market=MARKET,
            )
        except Exception as e:
            print(
                f"Feltöltési keresési hiba: {e}"
            )
            break

        for track in result[
            "tracks"
        ]["items"]:
            if len(rows) >= TARGET_TOTAL:
                break

            if has_bad_word(
                track["name"]
            ):
                continue

            year = track_year(track)

            if year is None:
                continue

            if not (
                start_year
                <= year
                <= end_year
            ):
                continue

            if (
                int(
                    track.get(
                        "popularity",
                        0,
                    )
                )
                < 45
            ):
                continue

            artist = compact_artists(track)
            key = song_key(
                artist,
                track["name"],
            )

            if key in known_keys:
                continue

            known_keys.add(key)

            rows.append(
                {
                    "artist": artist,
                    "title": track["name"],
                    "year": year,
                    "decade": get_decade(year),
                    "style": "Vegyes",
                    "language": "international",
                    "spotify_uri": track["uri"],
                    "spotify_popularity": (
                        track.get(
                            "popularity",
                            "",
                        )
                    ),
                    "year_source": "spotify",
                    "needs_year_review": (
                        "yes"
                        if soft_penalty(
                            track["name"]
                        )
                        else "no"
                    ),
                }
            )

        round_index += 1

        if round_index > 80:
            break

        time.sleep(0.05)


def write_output(rows):
    rows.sort(
        key=lambda row: (
            int(row["year"]),
            normalize(row["artist"]),
            normalize(row["title"]),
        )
    )

    fieldnames = [
        "artist",
        "title",
        "year",
        "decade",
        "style",
        "language",
        "spotify_uri",
        "spotify_popularity",
        "year_source",
        "needs_year_review",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    print("\n==========================")
    print("KÉSZ")
    print("==========================")
    print(f"Dalok összesen: {len(rows)}")

    missing_uri = sum(
        not row.get("spotify_uri")
        for row in rows
    )

    print(
        f"Spotify URI nélkül: "
        f"{missing_uri}"
    )

    review = sum(
        row.get(
            "needs_year_review"
        ) == "yes"
        for row in rows
    )

    print(
        f"Évszám-ellenőrzésre jelölve: "
        f"{review}"
    )

    decades = Counter(
        row["decade"]
        for row in rows
    )

    print("\nÉvtizedek:")

    for decade in sorted(decades):
        print(
            f"  {decade}: "
            f"{decades[decade]}"
        )

    styles = Counter(
        row["style"]
        for row in rows
    )

    print("\nStílusok:")

    for style, count in styles.most_common():
        print(
            f"  {style}: {count}"
        )

    print(
        f"\nFájl: {OUTPUT_FILE}"
    )


# ============================================================
# FUTTATÁS
# ============================================================

if __name__ == "__main__":
    if not Path(PLAN_FILE).exists():
        raise FileNotFoundError(
            f"Hiányzik: {PLAN_FILE}"
        )

    spotify = authenticate()

    rows = read_base_rows()
    rows = resolve_base_rows(
        spotify,
        rows,
    )

    known_keys = {
        song_key(
            row["artist"],
            row["title"],
        )
        for row in rows
    }

    # Először teszünk hozzá több magyar számot.
    add_hungarian_tracks(
        spotify,
        rows,
        known_keys,
        target_new=170,
    )

    # Utána évtized/stílus alapján töltjük fel.
    plan = read_plan()

    add_international_tracks(
        spotify,
        rows,
        known_keys,
        plan,
    )

    # Ha a genre keresések nem adtak elég dalt,
    # általános, népszerű találatokkal feltöltjük.
    if len(rows) < TARGET_TOTAL:
        broad_fill(
            spotify,
            rows,
            known_keys,
        )

    # Pontosan a célméretig tartjuk.
    rows = rows[:TARGET_TOTAL]

    write_output(rows)
    print_summary(rows)
