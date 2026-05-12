"""
Spotify tools — playback control, search, playlists, and library via Spotify Web API.

OAuth2 Authorization Code flow. Credentials stored in config/spotify_token.json.
Requires a Spotify Developer app: https://developer.spotify.com/dashboard
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import logging
import threading
import time
import urllib.request
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger("workstation-agent.spotify")

CONFIG_DIR = Path(__file__).parent.parent / "config"
SPOTIFY_CREDENTIALS_FILE = CONFIG_DIR / "spotify_credentials.json"
SPOTIFY_TOKEN_FILE = CONFIG_DIR / "spotify_token.json"

API_BASE = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
    "user-top-read",
    "user-library-read",
    "user-library-modify",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class SpotifyAuth:
    """Handles Spotify OAuth2 Authorization Code flow with token refresh."""

    def __init__(self):
        self._token_data: dict = {}
        self._client_id: str = ""
        self._client_secret: str = ""
        self._load_credentials()

    def _load_credentials(self):
        creds = _load_json(SPOTIFY_CREDENTIALS_FILE)
        self._client_id = creds.get("client_id", "")
        self._client_secret = creds.get("client_secret", "")
        self._token_data = _load_json(SPOTIFY_TOKEN_FILE)

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token_data.get("access_token"))

    def get_auth_url(self, redirect_uri: str = "http://127.0.0.1:8888/callback") -> str:
        params = urllib.parse.urlencode({
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "show_dialog": "true",
        })
        return f"{AUTH_URL}?{params}"

    def exchange_code(self, code: str, redirect_uri: str = "http://127.0.0.1:8888/callback") -> dict:
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            self._token_data = json.loads(resp.read().decode())
        self._token_data["obtained_at"] = int(time.time())
        _save_json(SPOTIFY_TOKEN_FILE, self._token_data)
        return {"status": "authenticated", "expires_in": self._token_data.get("expires_in")}

    def _refresh_token(self):
        refresh = self._token_data.get("refresh_token")
        if not refresh:
            raise RuntimeError("No refresh token available. Re-authenticate with Spotify.")
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            new_data = json.loads(resp.read().decode())
        # Spotify may or may not return a new refresh token
        if "refresh_token" not in new_data:
            new_data["refresh_token"] = refresh
        new_data["obtained_at"] = int(time.time())
        self._token_data = new_data
        _save_json(SPOTIFY_TOKEN_FILE, self._token_data)

    def authorize_interactive(self, port: int = 8888, timeout: int = 120) -> dict:
        """Open browser for Spotify auth and capture the callback automatically.

        Starts a temporary local HTTP server, opens the auth URL, waits for
        Spotify to redirect back with the code, exchanges it, and shuts down.
        """
        if not self.is_configured:
            raise RuntimeError(
                "Spotify not configured. Save client_id and client_secret "
                "to config/spotify_credentials.json"
            )

        redirect_uri = f"http://127.0.0.1:{port}/callback"
        captured: dict = {}

        class _CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                if "code" in params:
                    captured["code"] = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h2>Spotify authorized!</h2>"
                        b"<p>You can close this tab.</p></body></html>"
                    )
                elif "error" in params:
                    captured["error"] = params["error"][0]
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h2>Authorization failed</h2></body></html>"
                    )
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # suppress console noise

        server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
        server.timeout = timeout

        auth_url = self.get_auth_url(redirect_uri)
        logger.info("Opening Spotify auth URL in browser")
        webbrowser.open(auth_url)

        # Wait for the callback (blocking, with timeout)
        while not captured:
            server.handle_request()

        server.server_close()

        if "error" in captured:
            raise RuntimeError(f"Spotify authorization denied: {captured['error']}")

        return self.exchange_code(captured["code"], redirect_uri)

    def get_access_token(self) -> str:
        if not self.is_authenticated:
            raise RuntimeError(
                "Not authenticated with Spotify. "
                "Run spotify_authorize() to authenticate interactively."
            )
        # Refresh if token is expired or about to expire (60s buffer)
        obtained = self._token_data.get("obtained_at", 0)
        expires_in = self._token_data.get("expires_in", 3600)
        if time.time() > obtained + expires_in - 60:
            self._refresh_token()
        return self._token_data["access_token"]


class SpotifyTools:
    """Spotify Web API client for playback, search, playlists, and library."""

    def __init__(self, auth: SpotifyAuth):
        self._auth = auth

    def _request(self, method: str, endpoint: str, body: dict | None = None,
                 params: dict | None = None) -> dict | list | str:
        url = f"{API_BASE}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._auth.get_access_token()}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode()
                if not content:
                    return {"status": "ok"}
                return json.loads(content)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            try:
                error_json = json.loads(error_body)
                msg = error_json.get("error", {}).get("message", error_body)
            except (json.JSONDecodeError, AttributeError):
                msg = error_body
            return {"error": f"HTTP {e.code}: {msg}"}

    # ── Playback ──────────────────────────────────────────────

    def now_playing(self) -> dict:
        result = self._request("GET", "/me/player/currently-playing")
        if isinstance(result, dict) and result.get("status") == "ok":
            return {"playing": False, "message": "Nothing is currently playing."}
        if isinstance(result, dict) and "error" in result:
            return result
        if not isinstance(result, dict) or not result.get("item"):
            return {"playing": False, "message": "Nothing is currently playing."}

        item = result["item"]
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        progress_ms = result.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 0)

        return {
            "playing": result.get("is_playing", False),
            "track": item.get("name", ""),
            "artists": artists,
            "album": item.get("album", {}).get("name", ""),
            "progress": f"{progress_ms // 60000}:{(progress_ms // 1000) % 60:02d}",
            "duration": f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02d}",
            "device": result.get("device", {}).get("name", ""),
            "shuffle": result.get("shuffle_state", False),
            "repeat": result.get("repeat_state", "off"),
            "uri": item.get("uri", ""),
        }

    def play(self, uri: str = "", device_id: str = "") -> dict:
        params = {"device_id": device_id} if device_id else None
        body = None
        if uri:
            if uri.startswith("spotify:track:") or uri.startswith("spotify:episode:"):
                body = {"uris": [uri]}
            else:
                body = {"context_uri": uri}
        return self._request("PUT", "/me/player/play", body=body, params=params)

    def pause(self) -> dict:
        return self._request("PUT", "/me/player/pause")

    def next_track(self) -> dict:
        return self._request("POST", "/me/player/next")

    def previous_track(self) -> dict:
        return self._request("POST", "/me/player/previous")

    def set_volume(self, volume_percent: int) -> dict:
        volume_percent = max(0, min(100, volume_percent))
        return self._request("PUT", "/me/player/volume", params={"volume_percent": volume_percent})

    def shuffle(self, state: bool) -> dict:
        return self._request("PUT", "/me/player/shuffle", params={"state": str(state).lower()})

    def repeat(self, state: str) -> dict:
        if state not in ("track", "context", "off"):
            return {"error": "state must be 'track', 'context', or 'off'"}
        return self._request("PUT", "/me/player/repeat", params={"state": state})

    def queue_track(self, uri: str) -> dict:
        return self._request("POST", "/me/player/queue", params={"uri": uri})

    def get_queue(self) -> dict:
        result = self._request("GET", "/me/player/queue")
        if isinstance(result, dict) and "error" in result:
            return result
        currently = result.get("currently_playing")
        queue = result.get("queue", [])
        formatted = {
            "currently_playing": None,
            "queue": [],
        }
        if currently:
            artists = ", ".join(a["name"] for a in currently.get("artists", []))
            formatted["currently_playing"] = f"{currently.get('name', '')} - {artists}"
        for item in queue[:20]:
            artists = ", ".join(a["name"] for a in item.get("artists", []))
            formatted["queue"].append(f"{item.get('name', '')} - {artists}")
        return formatted

    def get_devices(self) -> list[dict]:
        result = self._request("GET", "/me/player/devices")
        if isinstance(result, dict) and "error" in result:
            return [result]
        devices = result.get("devices", [])
        return [
            {
                "id": d["id"],
                "name": d["name"],
                "type": d["type"],
                "active": d["is_active"],
                "volume": d.get("volume_percent"),
            }
            for d in devices
        ]

    def transfer_playback(self, device_id: str) -> dict:
        return self._request("PUT", "/me/player", body={"device_ids": [device_id]})

    # ── Search ────────────────────────────────────────────────

    def search(self, query: str, search_type: str = "track", limit: int = 10) -> list[dict]:
        valid_types = ("track", "artist", "album", "playlist")
        if search_type not in valid_types:
            return [{"error": f"type must be one of: {', '.join(valid_types)}"}]
        limit = max(1, min(50, limit))
        result = self._request("GET", "/search", params={
            "q": query,
            "type": search_type,
            "limit": limit,
            "market": "CA",
        })
        if isinstance(result, dict) and "error" in result:
            return [result]

        items_key = f"{search_type}s"
        items = result.get(items_key, {}).get("items", [])
        formatted = []
        for item in items:
            entry = {"name": item.get("name", ""), "uri": item.get("uri", "")}
            if search_type == "track":
                entry["artists"] = ", ".join(a["name"] for a in item.get("artists", []))
                entry["album"] = item.get("album", {}).get("name", "")
                dur = item.get("duration_ms", 0)
                entry["duration"] = f"{dur // 60000}:{(dur // 1000) % 60:02d}"
            elif search_type == "artist":
                entry["genres"] = item.get("genres", [])[:5]
                entry["followers"] = item.get("followers", {}).get("total", 0)
            elif search_type == "album":
                entry["artists"] = ", ".join(a["name"] for a in item.get("artists", []))
                entry["release_date"] = item.get("release_date", "")
                entry["total_tracks"] = item.get("total_tracks", 0)
            elif search_type == "playlist":
                entry["owner"] = item.get("owner", {}).get("display_name", "")
                entry["tracks"] = item.get("tracks", {}).get("total", 0)
            formatted.append(entry)
        return formatted

    # ── Playlists ─────────────────────────────────────────────

    def list_playlists(self, limit: int = 20) -> list[dict]:
        limit = max(1, min(50, limit))
        result = self._request("GET", "/me/playlists", params={"limit": limit})
        if isinstance(result, dict) and "error" in result:
            return [result]
        items = result.get("items", [])
        return [
            {
                "name": p["name"],
                "id": p["id"],
                "uri": p["uri"],
                "tracks": p.get("tracks", {}).get("total", 0),
                "public": p.get("public"),
                "owner": p.get("owner", {}).get("display_name", ""),
            }
            for p in items
        ]

    def get_playlist_tracks(self, playlist_id: str, limit: int = 50) -> list[dict]:
        limit = max(1, min(100, limit))
        result = self._request("GET", f"/playlists/{playlist_id}/tracks",
                               params={"limit": limit, "market": "CA"})
        if isinstance(result, dict) and "error" in result:
            return [result]
        items = result.get("items", [])
        tracks = []
        for item in items:
            t = item.get("track")
            if not t:
                continue
            artists = ", ".join(a["name"] for a in t.get("artists", []))
            tracks.append({
                "name": t.get("name", ""),
                "artists": artists,
                "album": t.get("album", {}).get("name", ""),
                "uri": t.get("uri", ""),
                "added_at": item.get("added_at", ""),
            })
        return tracks

    def create_playlist(self, name: str, description: str = "",
                        public: bool = False) -> dict:
        # Need user ID first
        me = self._request("GET", "/me")
        if isinstance(me, dict) and "error" in me:
            return me
        user_id = me.get("id", "")
        result = self._request("POST", f"/users/{user_id}/playlists", body={
            "name": name,
            "description": description,
            "public": public,
        })
        if isinstance(result, dict) and "error" in result:
            return result
        return {
            "name": result.get("name", ""),
            "id": result.get("id", ""),
            "uri": result.get("uri", ""),
            "url": result.get("external_urls", {}).get("spotify", ""),
        }

    def add_to_playlist(self, playlist_id: str, uris: list[str]) -> dict:
        return self._request("POST", f"/playlists/{playlist_id}/tracks",
                             body={"uris": uris})

    def remove_from_playlist(self, playlist_id: str, uris: list[str]) -> dict:
        tracks = [{"uri": uri} for uri in uris]
        return self._request("DELETE", f"/playlists/{playlist_id}/tracks",
                             body={"tracks": tracks})

    # ── Library ───────────────────────────────────────────────

    def recently_played(self, limit: int = 20) -> list[dict]:
        limit = max(1, min(50, limit))
        result = self._request("GET", "/me/player/recently-played",
                               params={"limit": limit})
        if isinstance(result, dict) and "error" in result:
            return [result]
        items = result.get("items", [])
        return [
            {
                "track": item["track"]["name"],
                "artists": ", ".join(a["name"] for a in item["track"].get("artists", [])),
                "played_at": item.get("played_at", ""),
                "uri": item["track"].get("uri", ""),
            }
            for item in items
        ]

    def top_tracks(self, time_range: str = "medium_term", limit: int = 20) -> list[dict]:
        if time_range not in ("short_term", "medium_term", "long_term"):
            return [{"error": "time_range must be short_term, medium_term, or long_term"}]
        limit = max(1, min(50, limit))
        result = self._request("GET", "/me/top/tracks",
                               params={"time_range": time_range, "limit": limit})
        if isinstance(result, dict) and "error" in result:
            return [result]
        return [
            {
                "name": t["name"],
                "artists": ", ".join(a["name"] for a in t.get("artists", [])),
                "album": t.get("album", {}).get("name", ""),
                "uri": t.get("uri", ""),
            }
            for t in result.get("items", [])
        ]

    def top_artists(self, time_range: str = "medium_term", limit: int = 20) -> list[dict]:
        if time_range not in ("short_term", "medium_term", "long_term"):
            return [{"error": "time_range must be short_term, medium_term, or long_term"}]
        limit = max(1, min(50, limit))
        result = self._request("GET", "/me/top/artists",
                               params={"time_range": time_range, "limit": limit})
        if isinstance(result, dict) and "error" in result:
            return [result]
        return [
            {
                "name": a["name"],
                "genres": a.get("genres", [])[:5],
                "followers": a.get("followers", {}).get("total", 0),
                "uri": a.get("uri", ""),
            }
            for a in result.get("items", [])
        ]

    def save_tracks(self, track_ids: list[str]) -> dict:
        return self._request("PUT", "/me/tracks", body={"ids": track_ids})

    def remove_saved_tracks(self, track_ids: list[str]) -> dict:
        return self._request("DELETE", "/me/tracks", body={"ids": track_ids})
