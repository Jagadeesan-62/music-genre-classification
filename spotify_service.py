import os
import time
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv


load_dotenv()


_original_getaddrinfo = socket.getaddrinfo


def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = ipv4_only_getaddrinfo


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"

_spotify_token = None
_spotify_token_expires_at = 0

_search_cache = {}
SEARCH_CACHE_TTL = 60 * 60

REQUEST_TIMEOUT = 10
TRACKS_PER_LANGUAGE = 10


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
        ),
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    _spotify_token = data["access_token"]
    _spotify_token_expires_at = current_time + data["expires_in"] - 60

    return _spotify_token


def search_language(token, language, genre, market):
    query = f"{language} genre:{genre}" if language else f"genre:{genre}"

    response = requests.get(
        SPOTIFY_SEARCH_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": query,
            "type": "track",
            "limit": TRACKS_PER_LANGUAGE,
            "market": market
        },
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    tracks = response.json()["tracks"]["items"]
    results = []
    seen_ids = set()

    for track in tracks:
        if track["id"] in seen_ids:
            continue

        seen_ids.add(track["id"])

        results.append({
            "id": track["id"],
            "language": language or None,
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
        })

    return results


def search_tracks(genre, market="US", languages=None):
    languages = languages or []

    languages = [
        language.strip()
        for language in languages
        if language.strip()
    ]

    languages = sorted(set(languages), key=str.lower)[:4]

    cache_key = (
        f"{market}:{genre}:"
        f"{','.join(language.lower() for language in languages)}"
    )

    cached = _search_cache.get(cache_key)

    if cached and time.time() < cached["expires_at"]:
        print("Spotify cache HIT:", cache_key)
        return cached["tracks"]

    print("Spotify cache MISS:", cache_key)

    token = get_spotify_token()

    if not languages:
        try:
            general_tracks = search_language(
                token,
                "",
                genre,
                market
            )
        except requests.RequestException as error:
            print(f"Spotify search failed: {error}")
            general_tracks = []

        tracks = {"General": general_tracks}

        _search_cache[cache_key] = {
            "tracks": tracks,
            "expires_at": time.time() + SEARCH_CACHE_TTL
        }

        return tracks

    results = {}

    with ThreadPoolExecutor(max_workers=len(languages)) as executor:
        futures = {
            executor.submit(
                search_language,
                token,
                language,
                genre,
                market
            ): language
            for language in languages
        }

        for future in as_completed(futures):
            language = futures[future]

            try:
                results[language] = future.result()
            except requests.RequestException as error:
                print(
                    f"Spotify search failed for "
                    f"{language}: {error}"
                )
                results[language] = []

    _search_cache[cache_key] = {
        "tracks": results,
        "expires_at": time.time() + SEARCH_CACHE_TTL
    }

    return results