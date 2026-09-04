import streamlit as st
import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SPOTIFY_SCOPE = "user-read-playback-state user-modify-playback-state"

sp_oauth = SpotifyOAuth(
    client_id=st.secrets["SPOTIFY_CLIENT_ID"],
    client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"],
    redirect_uri=st.secrets["SPOTIFY_REDIRECT_URI"],
    scope=SPOTIFY_SCOPE,
    cache_path=None,
)

SONGS = [
    {"artist": "Lady Gaga", "title": "Poker Face", "year": 2008},
    {"artist": "Britney Spears", "title": "...Baby One More Time", "year": 1998},
    {"artist": "ABBA", "title": "Dancing Queen", "year": 1976},
    {"artist": "Gotye feat. Kimbra", "title": "Somebody That I Used to Know", "year": 2011},
    {"artist": "The Weeknd", "title": "Blinding Lights", "year": 2019},
    {"artist": "a-ha", "title": "Take on Me", "year": 1985},
    {"artist": "Spice Girls", "title": "Wannabe", "year": 1996},
    {"artist": "Outkast", "title": "Hey Ya!", "year": 2003},
    {"artist": "Adele", "title": "Rolling in the Deep", "year": 2010},
    {"artist": "Billie Eilish", "title": "bad guy", "year": 2019},
]

st.set_page_config(
    page_title="Homemade Hitster",
    page_icon="🎵",
)

if "remaining_songs" not in st.session_state:
    st.session_state.remaining_songs = SONGS.copy()

if "current_song" not in st.session_state:
    st.session_state.current_song = None

if "revealed" not in st.session_state:
    st.session_state.revealed = False

# Spotify bejelentkezés
if "spotify_token_info" not in st.session_state:
    st.session_state.spotify_token_info = None

code = st.query_params.get("code")

if code and st.session_state.spotify_token_info is None:
    try:
        token_info = sp_oauth.get_access_token(
            code,
            check_cache=False
        )

        st.session_state.spotify_token_info = token_info

    except Exception as e:
        st.error("Nem sikerült a Spotify bejelentkezés.")
        st.exception(e)
        st.stop()

if st.session_state.spotify_token_info is None:
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
    auth=st.session_state.spotify_token_info["access_token"]
)

# Spotify eszközök tesztelése
st.subheader("Spotify kapcsolat teszt")

try:
    devices = spotify.devices()

    if devices["devices"]:
        st.success("✅ Spotify kapcsolat működik!")

        for device in devices["devices"]:
            st.write(
                f"🎧 {device['name']} "
                f"({'aktív' if device['is_active'] else 'nem aktív'})"
            )
    else:
        st.warning("Nem látok aktív Spotify-eszközt.")

except Exception as e:
    st.error("Nem sikerült lekérni a Spotify-eszközöket.")
    st.exception(e)

st.title("🎵 Homemade Hitster")

played = len(SONGS) - len(st.session_state.remaining_songs)
st.write(f"Lejátszott számok: **{played} / {len(SONGS)}**")


if st.session_state.current_song is None:

    if st.session_state.remaining_songs:

        if st.button("🎵 ÚJ SZÁM", use_container_width=True):

            song = random.choice(st.session_state.remaining_songs)

            st.session_state.current_song = song
            st.session_state.remaining_songs.remove(song)
            st.session_state.revealed = False

            st.rerun()

    else:
        st.success("Elfogytak a számok! 🎉")

else:

    if not st.session_state.revealed:

        st.info("🎶 A szám ki van választva.")

        if st.button("👀 MUTASD!", use_container_width=True):
            st.session_state.revealed = True
            st.rerun()

    else:

        song = st.session_state.current_song

        st.header(song["title"])
        st.subheader(song["artist"])
        st.metric("Megjelenés éve", song["year"])

        if st.button("➡️ KÖVETKEZŐ", use_container_width=True):

            st.session_state.current_song = None
            st.session_state.revealed = False

            st.rerun()