import streamlit as st
import random
import csv
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler


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

cache_handler = CacheFileHandler(
    cache_path=".spotify_cache"
)

sp_oauth = SpotifyOAuth(
    client_id=st.secrets["SPOTIFY_CLIENT_ID"],
    client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"],
    redirect_uri=st.secrets["SPOTIFY_REDIRECT_URI"],
    scope=SPOTIFY_SCOPE,
    cache_handler=cache_handler,
    requests_timeout=10,
    open_browser=False,
)


# -------------------------
# Dalok
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
# Spotify bejelentkezés
# -------------------------

token_info = sp_oauth.validate_token(
    cache_handler.get_cached_token()
)

code = st.query_params.get("code")


if token_info is None and code:

    try:
        token_info = sp_oauth.get_access_token(
            code,
            check_cache=False
        )

    except Exception as e:
        st.error("Nem sikerült a Spotify bejelentkezés.")
        st.exception(e)
        st.stop()


if token_info is None:

    auth_url = sp_oauth.get_authorize_url()

    st.title("🎵 Homemade Hitster")
    st.write("Először csatlakoztasd a Spotify-fiókodat.")

    st.link_button(
        "🟢 Belépés Spotifyba",
        auth_url,
        use_container_width=True
    )

    st.stop()


spotify = spotipy.Spotify(
    auth_manager=sp_oauth,
    requests_timeout=10,
)


# -------------------------
# Játék állapota
# -------------------------

if "remaining_songs" not in st.session_state:
    st.session_state.remaining_songs = SONGS.copy()

if "current_song" not in st.session_state:
    st.session_state.current_song = None

if "revealed" not in st.session_state:
    st.session_state.revealed = False


# -------------------------
# Spotify kapcsolat
# -------------------------

st.success("✅ Spotify csatlakoztatva")

try:
    devices = spotify.devices()

    if devices["devices"]:

        for device in devices["devices"]:
            st.write(
                f"🎧 {device['name']} "
                f"({'aktív' if device['is_active'] else 'nem aktív'})"
            )

    else:
        st.warning(
            "Nem látok Spotify-eszközt. "
            "Nyisd meg a Spotifyt valamelyik eszközödön."
        )

except Exception as e:
    st.error("Nem sikerült lekérni a Spotify-eszközöket.")
    st.exception(e)


# -------------------------
# Játék
# -------------------------

st.title("🎵 Homemade Hitster")

played = len(SONGS) - len(
    st.session_state.remaining_songs
)

st.write(
    f"Lejátszott számok: **{played} / {len(SONGS)}**"
)


if st.session_state.current_song is None:

    if st.session_state.remaining_songs:

        if st.button(
            "🎵 ÚJ SZÁM",
            use_container_width=True
        ):

            song = random.choice(
                st.session_state.remaining_songs
            )

            try:
                spotify.start_playback(
                    uris=[song["spotify_uri"]]
                )

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

            st.session_state.revealed = False

            st.rerun()

    else:

        st.success("Elfogytak a számok! 🎉")


else:

    if not st.session_state.revealed:

        st.info("🎶 A szám szól...")

        if st.button(
            "👀 MUTASD!",
            use_container_width=True
        ):

            st.session_state.revealed = True

            st.rerun()

    else:

        song = st.session_state.current_song

        st.header(song["title"])
        st.subheader(song["artist"])

        st.metric(
            "Megjelenés éve",
            song["year"]
        )

        if st.button(
            "➡️ KÖVETKEZŐ",
            use_container_width=True
        ):

            st.session_state.current_song = None
            st.session_state.revealed = False

            st.rerun()