import os
import requests
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

def get_spotify_token():
    response = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "client_credentials"
        },
        auth=(
            os.environ["SPOTIFY_CLIENT_ID"],
            os.environ["SPOTIFY_CLIENT_SECRET"]
        )
    )

    response.raise_for_status()

    return response.json()["access_token"]

def search_tracks(genre, limit=10):
    token = get_spotify_token()

    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={
            "Authorization": f"Bearer {token}"
        },
        params={
            "q": f"genre:{genre}",
            "type": "track",
            "limit": limit,
            "market": "US"
        }
    )

    response.raise_for_status()

    tracks = response.json()["tracks"]["items"]

    return [
        {
            "name": track["name"],
            "artist": ", ".join(
                artist["name"] for artist in track["artists"]
            ),
            "album": track["album"]["name"],
            "image": (
                track["album"]["images"][0]["url"]
                if track["album"]["images"]
                else None
            ),
            "spotify_url": track["external_urls"]["spotify"]
        }
        for track in tracks
    ]