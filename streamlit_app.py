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


def sorted_timeline(timeline):
    return sorted(
        timeline,
        key=lambda song: song["year"]
    )


def placement_is_correct(timeline, position, year):

    if position > 0:
        left_year = timeline[position - 1]["year"]

        if year < left_year:
            return False

    if position < len(timeline):
        right_year = timeline[position]["year"]

        if year > right_year:
            return False

    return True


def start_new_game(number_of_teams):

    remaining = SONGS.copy()

    teams = []

    for team_number in range(1, number_of_teams + 1):

        start_card = random.choice(remaining)
        remaining.remove(start_card)

        teams.append(
            {
                "name": f"{team_number}. csapat",
                "timeline": [start_card],
            }
        )

    st.session_state.teams = teams
    st.session_state.remaining_songs = remaining
    st.session_state.active_team_index = 0

    st.session_state.current_song = None
    st.session_state.selected_position = None
    st.session_state.revealed = False
    st.session_state.last_result = None

    st.session_state.game_started = True


def reset_game():

    keys_to_delete = [
        "teams",
        "remaining_songs",
        "active_team_index",
        "current_song",
        "selected_position",
        "revealed",
        "last_result",
    ]

    for key in keys_to_delete:

        if key in st.session_state:
            del st.session_state[key]

    st.session_state.game_started = False


# -------------------------
# Alap állapot
# -------------------------

if "game_started" not in st.session_state:
    st.session_state.game_started = False


# -------------------------
# Fejléc
# -------------------------

st.title("🎵 Homemade Hitster")

st.success("✅ Spotify csatlakoztatva")


# -------------------------
# Kezdőképernyő
# -------------------------

if not st.session_state.game_started:

    st.header("🎮 Új játék")

    st.write(
        "Válasszátok ki, hány csapat játszik."
    )

    number_of_teams = st.selectbox(
        "Csapatok száma",
        options=[2, 3, 4, 5, 6],
        index=0,
    )

    if st.button(
        "🎮 JÁTÉK INDÍTÁSA",
        use_container_width=True,
        type="primary",
    ):

        start_new_game(number_of_teams)

        st.rerun()

    st.stop()


# -------------------------
# Játék közbeni fejléc
# -------------------------

teams = st.session_state.teams

active_team_index = (
    st.session_state.active_team_index
)

active_team = teams[active_team_index]

st.caption(
    f"Hátralévő dalok: "
    f"{len(st.session_state.remaining_songs)}"
)


# -------------------------
# Csapatok
# -------------------------

st.subheader("🏆 Csapatok")

for index, team in enumerate(teams):

    timeline = sorted_timeline(
        team["timeline"]
    )

    timeline_text = "  ·  ".join(
        str(song["year"])
        for song in timeline
    )

    if index == active_team_index:
        marker = "👉 "
    else:
        marker = ""

    st.markdown(
        f"### {marker}{team['name']} "
        f"— {len(team['timeline'])} pont"
    )

    st.write(timeline_text)


st.divider()


# -------------------------
# Aktuális csapat
# -------------------------

st.header(
    f"🎯 {active_team['name']} következik"
)


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
            active_team["timeline"]
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

                left = (
                    timeline[position - 1]["year"]
                )

                right = (
                    timeline[position]["year"]
                )

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


        if (
            st.session_state.selected_position
            is not None
        ):

            st.success(
                "Hely kiválasztva."
            )

            if st.button(
                "👀 MUTASD!",
                use_container_width=True,
                type="primary",
            ):

                timeline = sorted_timeline(
                    active_team["timeline"]
                )

                correct = placement_is_correct(
                    timeline,
                    st.session_state.selected_position,
                    song["year"],
                )

                st.session_state.last_result = (
                    correct
                )

                if correct:

                    st.session_state.teams[
                        active_team_index
                    ]["timeline"].append(
                        song
                    )

                st.session_state.revealed = True

                st.rerun()


    # -------------------------
    # Felfedés
    # -------------------------

    else:

        if st.session_state.last_result:

            st.success(
                "🎉 HELYES! +1 pont"
            )

        else:

            st.error(
                "❌ Nem talált!"
            )


        st.header(
            song["title"]
        )

        st.subheader(
            song["artist"]
        )

        st.metric(
            "Megjelenés éve",
            song["year"],
        )


        timeline = sorted_timeline(
            st.session_state.teams[
                active_team_index
            ]["timeline"]
        )

        st.subheader(
            f"{active_team['name']} idővonala"
        )

        timeline_text = "  →  ".join(
            str(item["year"])
            for item in timeline
        )

        st.write(
            timeline_text
        )


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

            st.session_state.active_team_index = (
                active_team_index + 1
            ) % len(
                st.session_state.teams
            )

            st.session_state.current_song = None
            st.session_state.selected_position = None
            st.session_state.revealed = False
            st.session_state.last_result = None

            st.rerun()


# -------------------------
# Új játék
# -------------------------

st.divider()

if st.button(
    "🔄 ÚJ JÁTÉK",
    use_container_width=True,
):

    reset_game()

    st.rerun()