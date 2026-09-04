import csv
import random

import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth


st.set_page_config(
    page_title="Homemade Hitster",
    page_icon="🎵",
)


# -------------------------
# Spotify
# -------------------------

SPOTIFY_SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state"
)

sp_oauth = SpotifyOAuth(
    client_id=st.secrets["SPOTIFY_CLIENT_ID"],
    client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"],
    redirect_uri=st.secrets["SPOTIFY_REDIRECT_URI"],
    scope=SPOTIFY_SCOPE,
    cache_path=None,
    open_browser=False,
    requests_timeout=10,
)

try:
    token_info = sp_oauth.refresh_access_token(
        st.secrets["SPOTIFY_REFRESH_TOKEN"]
    )

    spotify = spotipy.Spotify(
        auth=token_info["access_token"],
        requests_timeout=10,
    )

except Exception as e:
    st.error("Nem sikerült kapcsolódni a Spotifyhoz.")
    st.exception(e)
    st.stop()


# -------------------------
# Dalok betöltése
# -------------------------

with open("songs.csv", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    SONGS = [
        {
            "artist": row["artist"],
            "title": row["title"],
            "year": int(row["year"]),
            "spotify_uri": row["spotify_uri"],
        }
        for row in reader
    ]


# -------------------------
# Segédfüggvények
# -------------------------

def start_song(song):
    spotify.start_playback(
        uris=[song["spotify_uri"]]
    )


def placement_is_correct(timeline, position, year):
    """
    Megnézi, hogy a megadott év helyesen kerülne-e
    a kiválasztott pozícióba.

    Az azonos évszámok elfogadottak.
    """

    if position > 0:
        left_year = timeline[position - 1]["year"]

        if year < left_year:
            return False

    if position < len(timeline):
        right_year = timeline[position]["year"]

        if year > right_year:
            return False

    return True


def sorted_timeline(timeline):
    return sorted(
        timeline,
        key=lambda song: song["year"]
    )


# -------------------------
# Játék inicializálása
# -------------------------

if "game_initialized" not in st.session_state:

    remaining = SONGS.copy()

    team_1_start = random.choice(remaining)
    remaining.remove(team_1_start)

    team_2_start = random.choice(remaining)
    remaining.remove(team_2_start)

    st.session_state.remaining_songs = remaining

    st.session_state.team_1_timeline = [
        team_1_start
    ]

    st.session_state.team_2_timeline = [
        team_2_start
    ]

    st.session_state.active_team = 1

    st.session_state.current_song = None

    st.session_state.selected_position = None

    st.session_state.revealed = False

    st.session_state.last_result = None

    st.session_state.game_initialized = True


# -------------------------
# Aktuális csapat
# -------------------------

active_team = st.session_state.active_team

if active_team == 1:
    active_timeline = st.session_state.team_1_timeline
else:
    active_timeline = st.session_state.team_2_timeline


# -------------------------
# Fejléc
# -------------------------

st.title("🎵 Homemade Hitster")

st.success("✅ Spotify csatlakoztatva")


# -------------------------
# Csapatok idővonalai
# -------------------------

st.subheader(
    f"🔵 1. csapat — "
    f"{len(st.session_state.team_1_timeline)} pont"
)

team_1_text = "  ·  ".join(
    str(song["year"])
    for song in sorted_timeline(
        st.session_state.team_1_timeline
    )
)

st.write(team_1_text)


st.subheader(
    f"🟠 2. csapat — "
    f"{len(st.session_state.team_2_timeline)} pont"
)

team_2_text = "  ·  ".join(
    str(song["year"])
    for song in sorted_timeline(
        st.session_state.team_2_timeline
    )
)

st.write(team_2_text)

st.divider()


# -------------------------
# Ki következik?
# -------------------------

if active_team == 1:
    st.header("🔵 1. csapat következik")
else:
    st.header("🟠 2. csapat következik")


# -------------------------
# Nincs aktuális dal
# -------------------------

if st.session_state.current_song is None:

    if st.session_state.remaining_songs:

        if st.button(
            "🎵 ÚJ SZÁM",
            use_container_width=True,
            type="primary",
        ):

            song = random.choice(
                st.session_state.remaining_songs
            )

            try:
                start_song(song)

            except Exception as e:
                st.error(
                    "Nem sikerült elindítani a számot."
                )
                st.exception(e)
                st.stop()

            st.session_state.current_song = song

            st.session_state.remaining_songs.remove(
                song
            )

            st.session_state.selected_position = None
            st.session_state.revealed = False
            st.session_state.last_result = None

            st.rerun()

    else:
        st.success("Elfogytak a számok! 🎉")


# -------------------------
# Van aktuális dal
# -------------------------

else:

    song = st.session_state.current_song

    # Mindig legyen újraindítás
    if st.button(
        "🔄 ÚJRAINDÍTÁS",
        use_container_width=True,
    ):

        try:
            start_song(song)

        except Exception as e:
            st.error(
                "Nem sikerült újraindítani a számot."
            )
            st.exception(e)


    # -------------------------
    # Tippelés
    # -------------------------

    if not st.session_state.revealed:

        st.info(
            "🎶 Hallgassátok meg a számot, "
            "majd válasszátok ki a helyét!"
        )

        timeline = sorted_timeline(
            active_timeline
        )

        st.subheader("Hová kerüljön?")

        for position in range(
            len(timeline) + 1
        ):

            if position == 0:

                label = (
                    f"⬅️ {timeline[0]['year']} elé"
                )

            elif position == len(timeline):

                label = (
                    f"{timeline[-1]['year']} után ➡️"
                )

            else:

                left = timeline[position - 1]["year"]
                right = timeline[position]["year"]

                label = (
                    f"{left}  ➜  🎵  ➜  {right}"
                )

            if (
                st.session_state.selected_position
                == position
            ):

                label = "✅ " + label

            if st.button(
                label,
                key=f"position_{position}",
                use_container_width=True,
            ):

                st.session_state.selected_position = (
                    position
                )

                st.rerun()


        if st.session_state.selected_position is not None:

            st.success(
                "Hely kiválasztva. "
                "Most felfedhetitek a számot."
            )

            if st.button(
                "👀 MUTASD!",
                use_container_width=True,
                type="primary",
            ):

                timeline = sorted_timeline(
                    active_timeline
                )

                correct = placement_is_correct(
                    timeline,
                    st.session_state.selected_position,
                    song["year"],
                )

                st.session_state.last_result = correct

                if correct:

                    if active_team == 1:
                        st.session_state.team_1_timeline.append(
                            song
                        )

                    else:
                        st.session_state.team_2_timeline.append(
                            song
                        )

                st.session_state.revealed = True

                st.rerun()


    # -------------------------
    # Felfedés
    # -------------------------

    else:

        if st.session_state.last_result:

            st.success("🎉 HELYES! +1 pont")

        else:

            st.error("❌ Nem talált!")


        st.header(song["title"])
        st.subheader(song["artist"])

        st.metric(
            "Megjelenés éve",
            song["year"],
        )


        # Megmutatjuk, mi volt a tipp
        timeline = sorted_timeline(
            active_timeline
        )

        st.subheader("A csapat idővonala")

        timeline_text = "  →  ".join(
            str(item["year"])
            for item in timeline
        )

        st.write(timeline_text)


        # Felfedés után is újra lehessen indítani
        if st.button(
            "🔄 DAL ÚJRAINDÍTÁSA",
            use_container_width=True,
        ):

            try:
                start_song(song)

            except Exception as e:
                st.error(
                    "Nem sikerült újraindítani a számot."
                )
                st.exception(e)


        if st.button(
            "➡️ KÖVETKEZŐ CSAPAT",
            use_container_width=True,
            type="primary",
        ):

            if st.session_state.active_team == 1:
                st.session_state.active_team = 2
            else:
                st.session_state.active_team = 1

            st.session_state.current_song = None
            st.session_state.selected_position = None
            st.session_state.revealed = False
            st.session_state.last_result = None

            st.rerun()