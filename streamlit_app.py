import csv
import random
import secrets
import string

import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth
from supabase import create_client
st.set_page_config(
    page_title="Homemade Hitster",
    page_icon="🎵",
    layout="centered",
)


# -------------------------
# Supabase
# -------------------------

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"],
)


def generate_game_code():
    alphabet = string.ascii_uppercase + string.digits

    for _ in range(20):
        code = "".join(
            secrets.choice(alphabet)
            for _ in range(4)
        )

        existing = (
            supabase.table("games")
            .select("game_code")
            .eq("game_code", code)
            .execute()
            .data
        )

        if not existing:
            return code

    raise RuntimeError(
        "Nem sikerült egyedi játékkódot létrehozni."
    )


def get_shared_game(game_code):
    result = (
        supabase.table("games")
        .select("*")
        .eq("game_code", game_code)
        .execute()
        .data
    )

    if not result:
        return None

    return result[0]


def create_shared_game(game_code):
    game_data = {
        "game_code": game_code,
        "number_of_teams": len(st.session_state.teams),
        "teams": st.session_state.teams,
        "remaining_songs": st.session_state.remaining_songs,
        "active_team_index": st.session_state.active_team_index,
        "current_song": st.session_state.current_song,
        "selected_position": st.session_state.selected_position,
        "revealed": st.session_state.revealed,
        "last_result": st.session_state.last_result,
        "game_status": "playing",
    }

    supabase.table("games").insert(game_data).execute()


def update_shared_game(**fields):
    game_code = st.session_state.get("game_code")

    if not game_code:
        return

    (
        supabase.table("games")
        .update(fields)
        .eq("game_code", game_code)
        .execute()
    )


def apply_shared_game(game):
    st.session_state.teams = game["teams"]
    st.session_state.remaining_songs = game["remaining_songs"]
    st.session_state.active_team_index = game["active_team_index"]
    st.session_state.current_song = game["current_song"]
    st.session_state.selected_position = game["selected_position"]
    st.session_state.revealed = game["revealed"]
    st.session_state.last_result = game["last_result"]
    st.session_state.game_started = True


def load_shared_game(game_code):
    game = get_shared_game(game_code)

    if game is None:
        return False

    apply_shared_game(game)
    st.session_state.game_code = game_code
    st.session_state.is_host = False

    return True


def sync_from_shared_game():
    game_code = st.session_state.get("game_code")

    if not game_code:
        return None

    game = get_shared_game(game_code)

    if game is None:
        return None

    apply_shared_game(game)

    return game


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
            "decade": f"{(int(row['year']) // 10) * 10}s",
            "spotify_uri": row["spotify_uri"],
        }
        for row in reader
    ]


DECADES = [
    "1950s",
    "1960s",
    "1970s",
    "1980s",
    "1990s",
    "2000s",
    "2010s",
    "2020s",
]

DEFAULT_DECADE_COUNTS = {
    "1950s": 5,
    "1960s": 10,
    "1970s": 15,
    "1980s": 20,
    "1990s": 20,
    "2000s": 20,
    "2010s": 15,
    "2020s": 10,
}

AVAILABLE_BY_DECADE = {
    decade: sum(1 for song in SONGS if song["decade"] == decade)
    for decade in DECADES
}


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


def start_new_game(number_of_teams, decade_counts):
    selected_songs = []

    for decade in DECADES:
        wanted = decade_counts.get(decade, 0)

        decade_songs = [
            song
            for song in SONGS
            if song["decade"] == decade
        ]

        if wanted > 0:
            selected_songs.extend(
                random.sample(
                    decade_songs,
                    k=wanted,
                )
            )

    random.shuffle(selected_songs)

    if len(selected_songs) < number_of_teams:
        st.error(
            "Legalább annyi dalt válassz ki összesen, "
            "ahány csapat játszik."
        )
        return False

    remaining = selected_songs.copy()
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
    st.session_state.decade_counts = decade_counts

    return True


def reset_game():
    keys_to_delete = [
        "teams",
        "remaining_songs",
        "active_team_index",
        "current_song",
        "selected_position",
        "revealed",
        "last_result",
        "decade_counts",
        "game_code",
        "is_host",
        "selected_team_index",
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
    create_tab, join_tab = st.tabs(
        ["🎮 ÚJ JÁTÉK", "📱 CSATLAKOZÁS"]
    )

    with create_tab:
        st.header("🎮 Új játék")

        st.write(
            "Válasszátok ki a csapatok számát és azt, "
            "hány dalt szeretnétek az egyes évtizedekből."
        )

        number_of_teams = st.selectbox(
            "Csapatok száma",
            options=[2, 3, 4, 5, 6],
            index=0,
        )

        st.subheader("🎶 Dalok évtizedenként")

        st.caption(
            "A megadott mennyiséget minden új játék elején "
            "véletlenszerűen választja ki a teljes dalkészletből."
        )

        decade_counts = {}

        for decade in DECADES:
            available = AVAILABLE_BY_DECADE[decade]

            decade_counts[decade] = st.slider(
                f"{decade} — elérhető: {available}",
                min_value=0,
                max_value=available,
                value=min(
                    DEFAULT_DECADE_COUNTS[decade],
                    available,
                ),
                step=1,
                key=f"decade_count_{decade}",
            )

        total_selected = sum(decade_counts.values())

        st.info(
            f"🎵 Összesen {total_selected} dal kerül a játékba. "
            f"Ebből {number_of_teams} lesz kezdőkártya."
        )

        if st.button(
            "🎮 JÁTÉK LÉTREHOZÁSA",
            use_container_width=True,
            type="primary",
        ):
            started = start_new_game(
                number_of_teams,
                decade_counts,
            )

            if started:
                try:
                    game_code = generate_game_code()
                    create_shared_game(game_code)

                    st.session_state.game_code = game_code
                    st.session_state.is_host = True
                    st.rerun()

                except Exception as e:
                    reset_game()
                    st.error(
                        "Nem sikerült létrehozni a közös játékot."
                    )
                    st.exception(e)

    with join_tab:
        st.header("📱 Csatlakozás játékhoz")

        st.write(
            "Írd be a fő játékos telefonján megjelenő "
            "4 karakteres játékkódot."
        )

        join_code = st.text_input(
            "Játékkód",
            max_chars=4,
            placeholder="pl. K7F3",
        ).strip().upper()

        if st.button(
            "📱 CSATLAKOZÁS",
            use_container_width=True,
        ):
            if len(join_code) != 4:
                st.error("Adj meg egy 4 karakteres játékkódot.")

            else:
                try:
                    if load_shared_game(join_code):
                        st.rerun()
                    else:
                        st.error(
                            "Nem található ilyen játékkód."
                        )

                except Exception as e:
                    st.error(
                        "Nem sikerült csatlakozni a játékhoz."
                    )
                    st.exception(e)

    st.stop()


# -------------------------
# Játékállapot
# -------------------------

if "is_host" not in st.session_state:
    st.session_state.is_host = False

if not st.session_state.is_host:
    if "selected_team_index" not in st.session_state:
        st.header("📱 Melyik csapat vagytok?")

        team_options = {
            f"{team['emoji']} {team['name']}": index
            for index, team in enumerate(st.session_state.teams)
        }

        selected_label = st.selectbox(
            "Csapat",
            options=list(team_options.keys()),
        )

        if st.button(
            "✅ EZ A MI CSAPATUNK",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.selected_team_index = (
                team_options[selected_label]
            )
            st.rerun()

        st.stop()


@st.fragment(run_every=1.5)
def render_synced_game():
    try:
        game = sync_from_shared_game()

    except Exception as e:
        st.error(
            "Nem sikerült frissíteni a közös játékállapotot."
        )
        st.exception(e)
        return

    if game is None:
        st.error("A játék már nem található.")
        return

    teams = st.session_state.teams
    active_team_index = st.session_state.active_team_index
    active_team = teams[active_team_index]
    is_host = st.session_state.is_host

    st.info(
        f"📱 Játékkód: **{st.session_state.game_code}**"
    )

    if is_host:
        st.caption("🎧 DJ / főképernyő")

    else:
        my_index = st.session_state.selected_team_index
        my_team = teams[my_index]

        st.caption(
            f"📱 Saját csapat: "
            f"{my_team['emoji']} {my_team['name']}"
        )

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
            Hátralévő dalok:
            {len(st.session_state.remaining_songs)}
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
            if is_host:
                if st.button(
                    "🎵 ÚJ SZÁM",
                    use_container_width=True,
                    type="primary",
                    key="host_new_song",
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
                        return

                    remaining = (
                        st.session_state.remaining_songs.copy()
                    )
                    remaining.remove(song)

                    update_shared_game(
                        current_song=song,
                        remaining_songs=remaining,
                        selected_position=None,
                        revealed=False,
                        last_result=None,
                    )

                    st.rerun(scope="fragment")

            else:
                st.info(
                    "🎧 A DJ indítja a következő számot."
                )

        else:
            st.success("Elfogytak a számok! 🎉")

        return

    # -------------------------
    # Van aktuális dal
    # -------------------------

    song = st.session_state.current_song

    if not st.session_state.revealed:
        st.info(
            "🎶 Hallgassátok meg a számot, "
            "majd az aktív csapat válassza ki a helyét!"
        )

        if is_host:
            if st.button(
                "🔄 DAL ÚJRAINDÍTÁSA",
                use_container_width=True,
                key="host_restart_hidden",
            ):
                try:
                    start_song(song)

                except Exception as e:
                    st.error(
                        "Nem sikerült újraindítani a számot."
                    )
                    st.exception(e)

        can_choose = (
            not is_host
            and st.session_state.selected_team_index
            == active_team_index
        )

        timeline = sorted_timeline(
            active_team["timeline"]
        )

        if can_choose:
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
                    key=f"team_position_{position}",
                    use_container_width=True,
                ):
                    update_shared_game(
                        selected_position=position
                    )
                    st.rerun(scope="fragment")

            if (
                st.session_state.selected_position
                is not None
            ):
                st.success("✅ Hely kiválasztva")

        elif not is_host:
            my_index = (
                st.session_state.selected_team_index
            )

            if my_index != active_team_index:
                st.info(
                    "⏳ Most egy másik csapat következik."
                )

        if is_host:
            if (
                st.session_state.selected_position
                is None
            ):
                st.warning(
                    "⏳ Az aktív csapat még nem választott helyet."
                )

            else:
                st.success(
                    "✅ Az aktív csapat kiválasztotta a helyét."
                )

                if st.button(
                    "👀 MUTASD!",
                    use_container_width=True,
                    type="primary",
                    key="host_reveal",
                ):
                    timeline = sorted_timeline(
                        active_team["timeline"]
                    )

                    correct = placement_is_correct(
                        timeline,
                        st.session_state.selected_position,
                        song["year"],
                    )

                    teams_copy = [
                        {
                            **team,
                            "timeline": team["timeline"].copy(),
                        }
                        for team in teams
                    ]

                    if correct:
                        teams_copy[
                            active_team_index
                        ]["timeline"].append(song)

                    update_shared_game(
                        teams=teams_copy,
                        last_result=correct,
                        revealed=True,
                    )

                    st.rerun(scope="fragment")

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
            f"{active_team['emoji']} "
            f"{active_team['name']} idővonala"
        )

        timeline = sorted_timeline(
            st.session_state.teams[
                active_team_index
            ]["timeline"]
        )

        years_html = "".join(
            f'<span class="year-chip">'
            f'{item["year"]}</span>'
            for item in timeline
        )

        st.markdown(
            f"""
            <div class="timeline"
                 style="justify-content:center;
                        margin-bottom:16px;">
                {years_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if is_host:
            if st.button(
                "🔄 DAL ÚJRAINDÍTÁSA",
                use_container_width=True,
                key="host_restart_revealed",
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
                key="host_next_team",
            ):
                next_team_index = (
                    active_team_index + 1
                ) % len(teams)

                update_shared_game(
                    active_team_index=next_team_index,
                    current_song=None,
                    selected_position=None,
                    revealed=False,
                    last_result=None,
                )

                st.rerun(scope="fragment")

        else:
            st.info(
                "🎧 A DJ lépteti tovább a játékot."
            )

    st.divider()

    if is_host:
        if st.button(
            "🔄 ÚJ JÁTÉK",
            use_container_width=True,
            key="host_reset_game",
        ):
            update_shared_game(
                game_status="finished"
            )
            reset_game()
            st.rerun()

    else:
        if st.button(
            "🚪 KILÉPÉS A JÁTÉKBÓL",
            use_container_width=True,
            key="client_leave_game",
        ):
            reset_game()
            st.rerun()


render_synced_game()
