import csv
import random
from io import BytesIO

import qrcode
import secrets
import string
import uuid
from datetime import datetime, timezone

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
            for _ in range(6)
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
        "host_id": st.session_state.device_id,
        "host_last_seen": utc_now_iso(),
        "steal_guesses": {},
        "token_awards": [],
        "final_round_start_team": None,
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
    st.session_state.steal_guesses = game.get("steal_guesses") or {}
    st.session_state.token_awards = game.get("token_awards") or []
    st.session_state.final_round_start_team = game.get("final_round_start_team")
    st.session_state.game_status = game.get("game_status", "playing")
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



HOST_TIMEOUT_SECONDS = 20


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value):
    if not value:
        return None

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def host_is_alive(game):
    host_id = game.get("host_id")
    last_seen = parse_utc(game.get("host_last_seen"))

    if not host_id or last_seen is None:
        return False

    age = (
        datetime.now(timezone.utc) - last_seen
    ).total_seconds()

    return age <= HOST_TIMEOUT_SECONDS


def claim_host_role():
    device_id = st.session_state.device_id

    update_shared_game(
        host_id=device_id,
        host_last_seen=utc_now_iso(),
    )

    st.session_state.is_host = True


def release_host_role():
    update_shared_game(
        host_id=None,
        host_last_seen=None,
    )
    st.session_state.is_host = False


# -------------------------
# QR-kód
# -------------------------

PUBLIC_APP_URL = "https://hotstar.streamlit.app"


def make_join_qr(game_code):
    join_url = f"{PUBLIC_APP_URL}/?join={game_code}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(join_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return join_url, buffer


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

COLOR_TEAM_NAMES = [
    "Kék csapat",
    "Narancs csapat",
    "Zöld csapat",
    "Lila csapat",
    "Piros csapat",
    "Sárga csapat",
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

        team_name = (
            "Kooperatív csapat"
            if number_of_teams == 1
            else COLOR_TEAM_NAMES[team_number - 1]
        )

        teams.append(
            {
                "name": team_name,
                "emoji": style["emoji"],
                "color": style["color"],
                "timeline": [start_card],
                "year_points": 0,
                "tokens": 0,
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
        "host_authenticated",
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
                {team['emoji']} {team['name']} — {team.get('year_points', max(0, len(team['timeline']) - 1)) + team.get('tokens', 0) // 3} pont · 🪙 {team.get('tokens', 0)} zseton
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

if "device_id" not in st.session_state:
    st.session_state.device_id = uuid.uuid4().hex


# -------------------------
# Fejléc
# -------------------------

st.title("🎵 Homemade Hitster")
st.caption("✅ Spotify csatlakoztatva")


# -------------------------
# Kezdőképernyő
# -------------------------

if not st.session_state.game_started:
    qr_join_code = st.query_params.get("join")

    if qr_join_code:
        qr_join_code = str(qr_join_code).strip().upper()

        if len(qr_join_code) == 6:
            try:
                if load_shared_game(qr_join_code):
                    st.query_params.clear()
                    st.rerun()
            except Exception:
                pass

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

        host_password = st.text_input(
            "Host jelszó",
            type="password",
            help="Csak a DJ-nek kell megadnia.",
        )

        number_of_teams = st.selectbox(
            "Játékmód / csapatok száma",
            options=[1, 2, 3, 4, 5, 6],
            index=1,
            format_func=lambda n: (
                "🤝 Kooperatív mód – 1 csapat"
                if n == 1
                else f"{n} csapat"
            ),
        )

        if number_of_teams == 1:
            st.caption(
                "🤝 Kooperatív mód: mindenki ugyanazért az egy csapatért játszik."
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
            expected_password = st.secrets.get("HOST_PASSWORD", "")

            if (
                not expected_password
                or not secrets.compare_digest(
                    host_password,
                    expected_password,
                )
            ):
                st.error("Hibás host jelszó.")

            else:
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
                        st.session_state.host_authenticated = True
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
            "6 karakteres játékkódot."
        )

        join_code = st.text_input(
            "Játékkód",
            max_chars=6,
            placeholder="pl. K7F3Q9",
        ).strip().upper()

        if st.button(
            "📱 CSATLAKOZÁS",
            use_container_width=True,
        ):
            if len(join_code) != 6:
                st.error("Adj meg egy 6 karakteres játékkódot.")

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
            st.session_state.selected_team_index = team_options[selected_label]
            st.rerun()

        st.stop()


def team_year_points(team):
    return team.get(
        "year_points",
        max(0, len(team.get("timeline", [])) - 1),
    )


def team_tokens(team):
    return team.get("tokens", 0)


def team_score(team):
    return team_year_points(team) + team_tokens(team) // 3


def normalized_teams(teams):
    result = []

    for team in teams:
        item = {
            **team,
            "timeline": team.get("timeline", []).copy(),
            "year_points": team_year_points(team),
            "tokens": team_tokens(team),
        }
        result.append(item)

    return result


def start_rematch(game):
    old_teams = normalized_teams(game["teams"])
    shifted_teams = (
        old_teams
        if len(old_teams) == 1
        else old_teams[1:] + old_teams[:1]
    )

    decade_counts = st.session_state.get(
        "decade_counts",
        DEFAULT_DECADE_COUNTS,
    )
    selected_songs = []

    for decade in DECADES:
        wanted = decade_counts.get(decade, 0)
        decade_songs = [
            song for song in SONGS
            if song["decade"] == decade
        ]
        if wanted > 0:
            selected_songs.extend(
                random.sample(decade_songs, k=wanted)
            )

    random.shuffle(selected_songs)

    if len(selected_songs) < len(shifted_teams):
        st.error("Nincs elég dal a visszavágóhoz.")
        return False

    remaining = selected_songs.copy()
    fresh_teams = []

    for team in shifted_teams:
        start_card = random.choice(remaining)
        remaining.remove(start_card)
        fresh_teams.append({
            **team,
            "timeline": [start_card],
            "year_points": 0,
            "tokens": 0,
        })

    update_shared_game(
        number_of_teams=len(fresh_teams),
        teams=fresh_teams,
        remaining_songs=remaining,
        active_team_index=0,
        current_song=None,
        selected_position=None,
        revealed=False,
        last_result=None,
        game_status="playing",
        steal_guesses={},
        token_awards=[],
        final_round_start_team=None,
    )

    # Keep this browser attached to the same COLOR team after order shifts.
    selected_index = st.session_state.get("selected_team_index")
    if selected_index is not None and selected_index < len(old_teams):
        selected_name = old_teams[selected_index]["name"]
        for new_index, team in enumerate(fresh_teams):
            if team["name"] == selected_name:
                st.session_state.selected_team_index = new_index
                break

    return True


def finish_game_if_needed(teams, active_team_index, final_round_start_team):
    """Return (status, final_round_start_team).

    A többcsapatos játék teljes körökben ér véget.
    Ha valaki eléri a 10 pontot, csak azok a csapatok kapnak még egy kört,
    akik az aktuális körben még nem játszottak.
    """
    if len(teams) == 1:
        if team_score(teams[0]) >= 10:
            return "finished", None
        return "playing", None

    if final_round_start_team is None:
        if not any(team_score(team) >= 10 for team in teams):
            return "playing", None

        # A normál kör a 0. indexű csapattal kezdődik.
        # Ha az utolsó csapat éri el a 10 pontot, mindenki már játszott
        # ebben a körben, ezért a játék azonnal véget ér.
        if active_team_index == len(teams) - 1:
            return "finished", None

        # A hátralévő csapatok még befejezik az aktuális kört.
        return "final_round", active_team_index

    # Már a befejező körben vagyunk. Az utolsó csapat után mindenki
    # ugyanannyi kört játszott, ezért lezárjuk a játékot.
    if active_team_index == len(teams) - 1:
        return "finished", final_round_start_team

    return "final_round", final_round_start_team


@st.fragment(run_every=1.5)
def render_synced_game():
    try:
        game = sync_from_shared_game()

    except Exception as e:
        st.error("Nem sikerült frissíteni a közös játékállapotot.")
        st.exception(e)
        return

    if game is None:
        st.error("A játék már nem található.")
        return

    teams = normalized_teams(st.session_state.teams)
    active_team_index = st.session_state.active_team_index
    active_team = teams[active_team_index]

    my_device_id = st.session_state.device_id
    current_host_id = game.get("host_id")
    is_host = (
        st.session_state.get("host_authenticated", False)
        and current_host_id == my_device_id
    )
    st.session_state.is_host = is_host

    st.info(f"📱 Játékkód: **{st.session_state.game_code}**")

    if is_host:
        st.caption("🎧 DJ / főképernyő")

        join_url, qr_buffer = make_join_qr(st.session_state.game_code)

        with st.expander("📱 QR-kód a csatlakozáshoz", expanded=True):
            st.image(
                qr_buffer,
                caption="A játékosok ezt olvassák be a telefonjukkal.",
                width=260,
            )
            st.caption(
                "A QR-kód automatikusan megnyitja ezt a játékot; "
                "a játékosnak már csak a csapatát kell kiválasztania."
            )

        with st.expander("🧪 Tesztelés", expanded=False):
            st.caption(
                "Csak a host látja. A soron lévő csapatot 7 évszám + "
                "9 zseton = 10 pontra állítja, így azonnal tesztelhető "
                "a játék vége anélkül, hogy végig kellene játszani."
            )

            if st.button(
                "🧪 SORON LÉVŐ CSAPAT → 10 PONT",
                use_container_width=True,
                key="host_test_set_10_points",
            ):
                latest = get_shared_game(st.session_state.game_code)
                test_teams = normalized_teams(latest["teams"])
                test_active = latest.get("active_team_index", 0)

                team = test_teams[test_active]
                timeline = team.get("timeline", [])

                # Keep the existing starting card and synthesize enough
                # harmless year-only entries for seven year points.
                if not timeline:
                    timeline = [{"year": 1950}]

                while len(timeline) < 8:
                    timeline.append(
                        {
                            "year": 1950 + len(timeline),
                            "artist": "Teszt",
                            "title": "Teszt",
                            "spotify_uri": "",
                        }
                    )

                team["timeline"] = timeline[:8]
                team["year_points"] = 7
                team["tokens"] = 9
                test_teams[test_active] = team

                update_shared_game(teams=test_teams)
                st.rerun(scope="fragment")

        host_team_options = {
            "🎧 Csak DJ vagyok": None,
            **{
                f"{team['emoji']} {team['name']}": index
                for index, team in enumerate(teams)
            },
        }

        current_host_team = st.session_state.get("selected_team_index")
        host_labels = list(host_team_options.keys())
        current_label_index = 0

        if current_host_team is not None:
            for label, index in host_team_options.items():
                if index == current_host_team:
                    current_label_index = host_labels.index(label)
                    break

        selected_host_label = st.selectbox(
            "A DJ játszik valamelyik csapatban?",
            options=host_labels,
            index=current_label_index,
            key="host_team_selector",
        )

        st.session_state.selected_team_index = host_team_options[selected_host_label]

    else:
        my_index = st.session_state.selected_team_index
        my_team = teams[my_index]
        st.caption(f"📱 Saját csapat: {my_team['emoji']} {my_team['name']}")

    # A DJ szerepet csak a host jelszóval játékot létrehozó eszköz kapja meg.

    # Finished game
    if game.get("game_status") == "finished":
        st.header("🏆 A JÁTÉK VÉGET ÉRT")

        scores = [team_score(team) for team in teams]
        best = max(scores)
        winners = [
            team for team in teams
            if team_score(team) == best
        ]

        if len(teams) == 1:
            st.success(
                f"🎉 SIKERÜLT! Elértétek a {best} pontot!"
            )
        elif len(winners) == 1:
            winner = winners[0]
            st.success(
                f"🏆 {winner['emoji']} {winner['name']} nyert "
                f"{best} ponttal!"
            )
        else:
            names = ", ".join(
                f"{team['emoji']} {team['name']}"
                for team in winners
            )
            st.success(f"🤝 Döntetlen: {names} — {best} pont")

        for index, team in enumerate(teams):
            render_timeline(team, active=False)

        if is_host:
            if st.button(
                "⚔️ VISSZAVÁGÓ",
                use_container_width=True,
                type="primary",
                key="finished_rematch",
            ):
                if start_rematch(game):
                    st.rerun(scope="fragment")

            if st.button(
                "🔄 TELJESEN ÚJ JÁTÉK",
                use_container_width=True,
                key="finished_new_game",
            ):
                reset_game()
                st.rerun()

        return

    if game.get("game_status") == "final_round":
        st.warning(
            "🏁 UTOLSÓ KÖR! Minden hátralévő csapat még egyszer jön, "
            "aztán vége a játéknak."
        )

    # Teams
    for index, team in enumerate(teams):
        render_timeline(team, active=(index == active_team_index))

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

    # No current song
    if st.session_state.current_song is None:
        if st.session_state.remaining_songs:
            if is_host:
                if st.button(
                    "🎵 ÚJ SZÁM",
                    use_container_width=True,
                    type="primary",
                    key="host_new_song",
                ):
                    song = random.choice(st.session_state.remaining_songs)

                    try:
                        start_song(song)
                    except Exception as e:
                        st.error("Nem sikerült elindítani a számot.")
                        st.exception(e)
                        return

                    remaining = st.session_state.remaining_songs.copy()
                    remaining.remove(song)

                    update_shared_game(
                        current_song=song,
                        remaining_songs=remaining,
                        selected_position=None,
                        revealed=False,
                        last_result=None,
                        steal_guesses={},
                        token_awards=[],
                    )
                    st.rerun(scope="fragment")
            else:
                st.info("🎧 A DJ indítja a következő számot.")
        else:
            st.success("Elfogytak a számok! 🎉")
        return

    song = st.session_state.current_song

    # Hidden song phase
    if not st.session_state.revealed:
        st.info(
            "🎶 Hallgassátok meg a számot, majd az aktív csapat "
            "válassza ki a helyét!"
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
                    st.error("Nem sikerült újraindítani a számot.")
                    st.exception(e)

            if st.button(
                "⏭️ EZ NEM JÓ — KÉREK ÚJ SZÁMOT",
                use_container_width=True,
                key="host_replace_song",
            ):
                # Discard this song for this game and draw a completely new one.
                update_shared_game(
                    current_song=None,
                    selected_position=None,
                    revealed=False,
                    last_result=None,
                    steal_guesses={},
                    token_awards=[],
                )
                st.rerun(scope="fragment")

        my_team_index = st.session_state.get("selected_team_index")
        can_choose = my_team_index == active_team_index
        active_timeline = sorted_timeline(active_team["timeline"])

        if can_choose:
            st.subheader("Hová kerüljön?")

            for position in range(len(active_timeline) + 1):
                if position == 0:
                    label = f"⬅️  {active_timeline[0]['year']} ELÉ"
                elif position == len(active_timeline):
                    label = f"{active_timeline[-1]['year']} UTÁN  ➡️"
                else:
                    left = active_timeline[position - 1]["year"]
                    right = active_timeline[position]["year"]
                    label = f"{left}   🎵   {right}"

                if st.session_state.selected_position == position:
                    label = "✅  " + label

                if st.button(
                    label,
                    key=f"team_position_{position}",
                    use_container_width=True,
                ):
                    update_shared_game(selected_position=position)
                    st.rerun(scope="fragment")

            if st.session_state.selected_position is not None:
                st.success("✅ Hely kiválasztva")

        # Robbery for non-active teams: costs one token immediately.
        if (
            len(teams) > 1
            and my_team_index is not None
            and my_team_index != active_team_index
        ):
            my_team = teams[my_team_index]
            steals = game.get("steal_guesses") or {}
            my_key = str(my_team_index)

            if my_key in steals:
                st.info("🪙 Rablási tipped leadva. A zseton elköltve.")
            elif team_tokens(my_team) > 0:
                with st.expander("🪙 RABLÁS — 1 zseton"):
                    st.caption(
                        "Ha szerintetek az aktív csapat rossz helyre tette, "
                        "1 zsetonért megjelölhetitek a helyes helyet a saját "
                        "idővonalatokon. A zseton mindenképp elveszik."
                    )

                    steal_reference_timeline = sorted_timeline(
                        active_team["timeline"]
                    )

                    for position in range(len(steal_reference_timeline) + 1):
                        if position == 0:
                            label = (
                                f"⬅️ {steal_reference_timeline[0]['year']} ELÉ"
                            )
                        elif position == len(steal_reference_timeline):
                            label = (
                                f"{steal_reference_timeline[-1]['year']} UTÁN ➡️"
                            )
                        else:
                            left = steal_reference_timeline[position - 1]["year"]
                            right = steal_reference_timeline[position]["year"]
                            label = f"{left} 🎵 {right}"

                        if st.button(
                            label,
                            key=f"steal_{my_team_index}_{position}",
                            use_container_width=True,
                        ):
                            latest = get_shared_game(st.session_state.game_code)
                            latest_steals = latest.get("steal_guesses") or {}
                            latest_teams = normalized_teams(latest["teams"])

                            if str(my_team_index) not in latest_steals:
                                latest_teams[my_team_index]["tokens"] -= 1
                                latest_steals[str(my_team_index)] = position

                                update_shared_game(
                                    teams=latest_teams,
                                    steal_guesses=latest_steals,
                                )
                            st.rerun(scope="fragment")
            else:
                st.caption("🪙 Rabláshoz legalább 1 zseton kell.")

        if is_host:
            if st.session_state.selected_position is None:
                st.warning("⏳ Az aktív csapat még nem választott helyet.")
            else:
                steals = game.get("steal_guesses") or {}
                if steals:
                    st.info(f"🪙 {len(steals)} csapat rablást jelentett be.")

                if st.button(
                    "👀 MUTASD!",
                    use_container_width=True,
                    type="primary",
                    key="host_reveal",
                ):
                    correct = placement_is_correct(
                        active_timeline,
                        st.session_state.selected_position,
                        song["year"],
                    )

                    teams_copy = normalized_teams(teams)

                    if correct:
                        teams_copy[active_team_index]["timeline"].append(song)
                        teams_copy[active_team_index]["year_points"] += 1

                    # Successful steal only if active team was wrong.
                    if not correct:
                        for team_key, position in (game.get("steal_guesses") or {}).items():
                            thief_index = int(team_key)
                            steal_reference_timeline = sorted_timeline(
                                active_team["timeline"]
                            )

                            if placement_is_correct(
                                steal_reference_timeline,
                                position,
                                song["year"],
                            ):
                                teams_copy[thief_index]["timeline"].append(song)
                                teams_copy[thief_index]["year_points"] += 1

                    update_shared_game(
                        teams=teams_copy,
                        last_result=correct,
                        revealed=True,
                    )
                    st.rerun(scope="fragment")

    # Reveal phase
    else:
        if st.session_state.last_result:
            st.success("🎉 HELYES! +1 évszám-pont")
        else:
            st.error("❌ NEM TALÁLT!")

        st.markdown(
            f"""
            <div class="song-title">{song['title']}</div>
            <div class="song-artist">{song['artist']}</div>
            <div class="big-year">{song['year']}</div>
            """,
            unsafe_allow_html=True,
        )

        # Show successful steals.
        steals = game.get("steal_guesses") or {}
        if steals and not st.session_state.last_result:
            successful = []
            for team_key, position in steals.items():
                idx = int(team_key)
                # If the song is now present, the steal succeeded.
                if any(
                    item.get("spotify_uri") == song.get("spotify_uri")
                    for item in teams[idx]["timeline"]
                ):
                    successful.append(
                        f"{teams[idx]['emoji']} {teams[idx]['name']}"
                    )

            if successful:
                st.success("🪙 Sikeres rablás: " + ", ".join(successful))

        if is_host:
            st.subheader("🪙 Ki találta el az előadót ÉS a szám címét?")
            st.caption(
                "A DJ zsetont adhat bármelyik csapatnak. "
                "3 meglévő zseton = 1 pont."
            )

            awarded = set(game.get("token_awards") or [])

            for index, team in enumerate(teams):
                already = index in awarded
                label = (
                    f"✅ {team['emoji']} {team['name']} — zseton megadva"
                    if already
                    else f"🪙 {team['emoji']} {team['name']} +1 zseton"
                )

                if st.button(
                    label,
                    key=f"award_token_{index}",
                    use_container_width=True,
                    disabled=already,
                ):
                    latest = get_shared_game(st.session_state.game_code)
                    latest_teams = normalized_teams(latest["teams"])
                    latest_awards = set(latest.get("token_awards") or [])

                    if index not in latest_awards:
                        latest_teams[index]["tokens"] += 1
                        latest_awards.add(index)

                        update_shared_game(
                            teams=latest_teams,
                            token_awards=sorted(latest_awards),
                        )
                    st.rerun(scope="fragment")

            if st.button(
                "🔄 DAL ÚJRAINDÍTÁSA",
                use_container_width=True,
                key="host_restart_revealed",
            ):
                try:
                    start_song(song)
                except Exception as e:
                    st.error("Nem sikerült újraindítani a számot.")
                    st.exception(e)

            if st.button(
                "➡️ KÖVETKEZŐ CSAPAT",
                use_container_width=True,
                type="primary",
                key="host_next_team",
            ):
                latest = get_shared_game(st.session_state.game_code)
                latest_teams = normalized_teams(latest["teams"])
                latest_active_team_index = latest.get(
                    "active_team_index",
                    0,
                )
                final_start = latest.get("final_round_start_team")

                status, final_start = finish_game_if_needed(
                    latest_teams,
                    latest_active_team_index,
                    final_start,
                )

                if status == "finished":
                    update_shared_game(
                        teams=latest_teams,
                        game_status="finished",
                        final_round_start_team=final_start,
                        current_song=None,
                        selected_position=None,
                        revealed=False,
                        last_result=None,
                        steal_guesses={},
                        token_awards=[],
                    )
                else:
                    next_team_index = (
                        latest_active_team_index + 1
                    ) % len(latest_teams)

                    update_shared_game(
                        teams=latest_teams,
                        game_status=status,
                        final_round_start_team=final_start,
                        active_team_index=next_team_index,
                        current_song=None,
                        selected_position=None,
                        revealed=False,
                        last_result=None,
                        steal_guesses={},
                        token_awards=[],
                    )

                st.rerun(scope="fragment")
        else:
            st.info("🎧 A DJ adhat zsetont és lépteti tovább a játékot.")

    st.divider()

    if is_host:
        if st.button(
            "🔄 ÚJ JÁTÉK",
            use_container_width=True,
            key="host_reset_game",
        ):
            update_shared_game(game_status="finished")
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
