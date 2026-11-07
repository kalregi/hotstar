"""Catalog filtering and sampling shared by game creation and rematches."""

import csv
import random


STYLE_GROUPS = {
    "Pop": {"Pop"},
    "Rock / Alternative": {"Rock", "Alternative", "New Wave", "Blues"},
    "Dance / Electronic / Disco": {"Dance", "Electronic", "Disco"},
    "Hip-hop": {"Hip-hop"},
    "Soul / R&B / Funk": {"Soul", "R&B", "Funk"},
    "Egyéb": {"Folk", "Country", "Latin Pop", "Latin", "Afrobeats",
              "Dancehall", "Reggae", "Comedy", "Jazz"},
    "Karácsonyi slágerek": {"Karácsonyi slágerek"},
}


def style_tags(style):
    tags = {tag.strip() for tag in style.split("/") if tag.strip()}
    # Curated describes the source of a song, rather than a musical genre.
    tags.discard("Curated")
    if "Rock & Roll" in tags:
        tags.remove("Rock & Roll")
        tags.add("Rock")
    return tags


def load_songs(path):
    with open(path, encoding="utf-8-sig", newline="") as file:
        return [
            {
                "artist": row["artist"],
                "title": row["title"],
                "year": int(row["year"]),
                "decade": f"{(int(row['year']) // 10) * 10}s",
                "style": row.get("style", ""),
                "difficulty": int(row["difficulty"]) if row.get("difficulty") else None,
                "language": row.get("language", ""),
                "spotify_uri": row["spotify_uri"],
            }
            for row in csv.DictReader(file)
        ]


def available_styles(songs):
    present = {group for song in songs for group in song_style_groups(song["style"])}
    return [group for group in STYLE_GROUPS if group in present]


def song_style_groups(style):
    tags = style_tags(style)
    groups = {name for name, members in STYLE_GROUPS.items() if tags & members}
    known_tags = set().union(*STYLE_GROUPS.values())
    if not tags or tags - known_tags:
        groups.add("Egyéb")
    return groups


def filter_songs(songs, selected_styles=(), selected_difficulties=(), selected_languages=()):
    """OR within each selection; AND between filters. Empty means unrestricted."""
    selected = set(selected_styles)
    difficulties = set(selected_difficulties)
    languages = set(selected_languages)
    # Retain support for saved games using the original, detailed style names.
    grouped = selected & STYLE_GROUPS.keys()
    legacy = selected - STYLE_GROUPS.keys()
    return [
        song for song in songs
        if (
            not selected
            or grouped & song_style_groups(song["style"])
            or legacy & style_tags(song["style"])
        )
        and (not difficulties or song.get("difficulty") in difficulties)
        and (not languages or song.get("language") in languages)
    ]


def sample_songs(songs, decade_counts, selected_styles=(), selected_difficulties=(), selected_languages=(), all_decades=False):
    pool = filter_songs(songs, selected_styles, selected_difficulties, selected_languages)
    if all_decades:
        random.shuffle(pool)
        return pool
    selected = []
    for decade, wanted in decade_counts.items():
        candidates = [song for song in pool if song["decade"] == decade]
        if wanted < 0 or wanted > len(candidates):
            raise ValueError(
                f"{decade}: {wanted} dalt kértél, de a választott "
                f"szűrőkkel csak {len(candidates)} érhető el."
            )
        selected.extend(random.sample(candidates, k=wanted))
    random.shuffle(selected)
    return selected


def shared_game_settings(game):
    # The existing teams JSON stores the settings without a database migration.
    # Find the owning team even after rematches rotate the starting order.
    for team in game["teams"]:
        if "game_settings" in team:
            return team["game_settings"]
    return None
