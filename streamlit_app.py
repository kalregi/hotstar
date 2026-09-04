import csv
import random

import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth


st.set_page_config(
    page_title="Homemade Hitster",
    page_icon="🎵",
    layout="centered",
)


# -------------------------
# Mobilbarát kinézet
# -------------------------

st.markdown(
    """
    <style>
        .block-container {
            max-width: 760px;
            padding-top: 1rem;
            padding-bottom: 2rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        h1 {
            font-size: 2rem !important;
            margin-bottom: 0.5rem !important;
        }

        h2 {
            font-size: 1.55rem !important;
        }

        h3 {
            font-size: 1.3rem !important;
        }

        .stButton > button {
            width: 100%;
            min-height: 64px;
            font-size: 1.15rem;
            font-weight: 700;
            border-radius: 14px;
        }

        div[data-baseweb="select"] {
            font-size: 1.1rem;
        }

        .team-card {
            border: 2px solid rgba(128, 128, 128, 0.25);
            border-radius: 16px;
            padding: 12px 14px;
            margin: 10px 0;
            background: rgba(128, 128, 128, 0.06);
        }

        .team-card.active {
            border-width: 3px;
        }

        .team-title {
            font-size: 1.15rem;
            font-weight: 800;
            margin-bottom: 8px;
        }

        .timeline {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }

        .year-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 72px;
            min-height: 54px;
            padding: 4px 10px;
            border-radius: 12px;
            border: 2px solid rgba(128, 128, 128, 0.35);
            background: rgba(128, 128, 128, 0.08);
            font-size: 1.65rem;
            line-height: 1;
            font-weight: 900;
            letter-spacing: 0.02em;
        }

        .current-team {
            text-align: center;
            padding: 14px 12px;
            border-radius: 16px;
            margin: 12px 0 18px 0;
            font-size: 1.45rem;
            font-weight: 900;
            background: rgba(128, 128, 128, 0.08);
        }

        .song-title {
            font-size: 2rem;
            line-height: 1.15;
            font-weight: 900;
            text-align: center;
            margin-top: 12px;
        }

        .song-artist {
            font-size: 1.35rem;
            text-align: center;
            margin-top: 6px;
            opacity: 0.85;
        }

        .big-year {
            text-align: center;
            font-size: 4rem;
            line-height: 1;
            font-weight: 900;
            margin: 18px 0;
        }

        .small-muted {
            text-align: center;
            opacity: 0.7;
            font-size: 0.95rem;
        }

        @media (max-width: 480px) {
            .block-container {
                padding-left: 0.55rem;
                padding-right: 0.55rem;
            }

            h1 {
                font-size: 1.75rem !important;
            }

            .stButton > button {
                min-height: 68px;
                font-size: 1.12rem;
            }

            .year-chip {
                min-width: 70px;
                min-height: 56px;
                font-size: 1.7rem;
            }

            .big-year {
                font-size: 4.4rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
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
# Csapatszínek
# -------------------------

TEAM_STYLES = [
    {"emoji": "🔵", "color": "#3B82F6"},
    {"emoji": "🟠", "color": "#F59E0B"},
    {"emoji": "🟢", "color": "#22C55E"},
    {"emoji": "🟣", "color": "#A855F7"},
    {"emoji": "🔴", "color": "#EF4444"},
    {"emoji": "🟡", "color": "#EAB308"},
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

        style = TEAM_STYLES[team_number - 1]

        teams.append(
            {
                "name": f"{team_number}. csapat",
                "emoji": style["emoji"],
                "color": style["color"],
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


def render_timeline(team, active=False):
    timeline = sorted_timeline(team["timeline"])

    years_html = "".join(
        f'<span class="year-chip">{song["year"]}</span>'
        for song in timeline
    )

    active_class = " active" if active else ""

    st.markdown(
        f"""
        <div class="team-card{active_class}"
             style="border-color: {team['color']};">
            <div class="team-title">
                {team['emoji']} {team['name']} — {len(team['timeline'])} pont
            </div>
            <div class="timeline">
                {years_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------
# Alap állapot
# -------------------------

if "game_started" not in st.session_state:
    st.session_state.game_started = False


# -------------------------
# Fejléc
# -------------------------

st.title("🎵 Homemade Hitster")
st.caption("✅ Spotify csatlakoztatva")


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
# Játékállapot
# -------------------------

teams = st.session_state.teams
active_team_index = st.session_state.active_team_index
active_team = teams[active_team_index]


# -------------------------
# Csapatok
# -------------------------

for index, team in enumerate(teams):
    render_timeline(
        team,
        active=(index == active_team_index),
    )


st.markdown(
    f"""
    <div class="current-team"
         style="border: 3px solid {active_team['color']};">
        🎯 {active_team['emoji']} {active_team['name']} következik
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="small-muted">
        Hátralévő dalok: {len(st.session_state.remaining_songs)}
    </div>
    """,
    unsafe_allow_html=True,
)


# -------------------------
# Nincs aktuális dal
# -------------------------

if st.session_state.current_song is None:
    st.write("")

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
            st.session_state.remaining_songs.remove(song)
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

    if not st.session_state.revealed:
        st.info(
            "🎶 Hallgassátok meg a számot, "
            "majd válasszátok ki a helyét!"
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

        timeline = sorted_timeline(
            active_team["timeline"]
        )

        st.subheader("Hová kerüljön?")

        for position in range(
            len(timeline) + 1
        ):
            if position == 0:
                label = (
                    f"⬅️  {timeline[0]['year']} ELÉ"
                )

            elif position == len(timeline):
                label = (
                    f"{timeline[-1]['year']} UTÁN  ➡️"
                )

            else:
                left = timeline[position - 1]["year"]
                right = timeline[position]["year"]

                label = (
                    f"{left}   🎵   {right}"
                )

            if (
                st.session_state.selected_position
                == position
            ):
                label = "✅  " + label

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
                "✅ Hely kiválasztva"
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

                st.session_state.last_result = correct

                if correct:
                    st.session_state.teams[
                        active_team_index
                    ]["timeline"].append(song)

                st.session_state.revealed = True
                st.rerun()


    # -------------------------
    # Felfedés
    # -------------------------

    else:
        if st.session_state.last_result:
            st.success("🎉 HELYES! +1 pont")
        else:
            st.error("❌ NEM TALÁLT!")

        st.markdown(
            f"""
            <div class="song-title">
                {song['title']}
            </div>
            <div class="song-artist">
                {song['artist']}
            </div>
            <div class="big-year">
                {song['year']}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader(
            f"{active_team['emoji']} {active_team['name']} idővonala"
        )

        timeline = sorted_timeline(
            st.session_state.teams[
                active_team_index
            ]["timeline"]
        )

        years_html = "".join(
            f'<span class="year-chip">{item["year"]}</span>'
            for item in timeline
        )

        st.markdown(
            f"""
            <div class="timeline"
                 style="justify-content:center; margin-bottom:16px;">
                {years_html}
            </div>
            """,
            unsafe_allow_html=True,
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
            ) % len(st.session_state.teams)

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
