import csv
from getpass import getpass
import spotipy
from spotipy.oauth2 import SpotifyOAuth

INPUT_FILE = "hitster_120_source.csv"
OUTPUT_FILE = "songs.csv"

client_id = input("Spotify Client ID: ").strip()
client_secret = getpass("Spotify Client Secret (nem fog látszani): ").strip()
refresh_token = getpass("Spotify Refresh Token (nem fog látszani): ").strip()

oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-read-playback-state user-modify-playback-state",
    cache_path=None,
    open_browser=False,
)
token_info = oauth.refresh_access_token(refresh_token)
spotify = spotipy.Spotify(auth=token_info["access_token"], requests_timeout=15)

rows = []
with open(INPUT_FILE, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        artist, title, year = row["artist"].strip(), row["title"].strip(), int(row["year"])
        result = spotify.search(q=f'track:"{title}" artist:"{artist}"', type="track", limit=5)
        items = result["tracks"]["items"]
        if not items:
            items = spotify.search(q=f"{artist} {title}", type="track", limit=5)["tracks"]["items"]
        uri = items[0]["uri"] if items else ""
        if items:
            print(f"OK: {artist} – {title} -> {items[0]['artists'][0]['name']} – {items[0]['name']}")
        else:
            print(f"NINCS TALÁLAT: {artist} – {title}")
        rows.append({"artist":artist,"title":title,"year":year,"spotify_uri":uri})

with open(OUTPUT_FILE,"w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=["artist","title","year","spotify_uri"])
    w.writeheader(); w.writerows(rows)

print(f"\nKész: {OUTPUT_FILE}")
print("Spotify URI nélkül:", sum(not r["spotify_uri"] for r in rows))
