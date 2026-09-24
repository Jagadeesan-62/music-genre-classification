import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

_spotify_token = None
_spotify_token_expires_at = 0

_search_cache = {}
SEARCH_CACHE_TTL = 60 * 60

def get_spotify_token():
    global _spotify_token, _spotify_token_expires_at

    current_time = time.time()

    if _spotify_token and current_time < _spotify_token_expires_at:
        return _spotify_token

    response = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(
            os.environ["SPOTIFY_CLIENT_ID"],
            os.environ["SPOTIFY_CLIENT_SECRET"]
        )
    )
    response.raise_for_status()

    data = response.json()

    _spotify_token = data["access_token"]
    _spotify_token_expires_at = current_time + data["expires_in"] - 60

    return _spotify_token

def search_tracks(genre, limit=10, market="US"):
    cache_key = f"{market}:{genre}:{limit}"
    current_time = time.time()

    cached = _search_cache.get(cache_key)

    if cached and current_time < cached["expires_at"]:
        return cached["tracks"]
    
    token = get_spotify_token()

    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"genre:{genre}",
            "type": "track",
            "limit": limit,
            "market": market
        }
    )
    response.raise_for_status()

    tracks = [
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
        for track in response.json()["tracks"]["items"]
    ]

    _search_cache[cache_key] = {
        "tracks": tracks,
        "expires_at": current_time + SEARCH_CACHE_TTL
    }

    return tracks