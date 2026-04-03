"""
Phase 5 scraper: Spotify Web API enrichment via Client Credentials flow.

Enriches existing Song rows with:
  - duration_seconds
  - spotify_id
  - isrc

Does NOT require user login. Uses Client ID + Secret from .env only.
"""
import os
import time

import requests
from sqlalchemy.orm import Session

from app.models.songs import Song


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"


class SpotifyScraper:

    def __init__(self):
        self.client_id = os.environ["SPOTIFY_CLIENT_ID"]
        self.client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
        self._token: str | None = None
        self._token_expiry: float = 0

    def _get_token(self) -> str:
        """Request a new Client Credentials token if the current one has expired."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        response = requests.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data["expires_in"] - 60  # 60s buffer
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def search_track(self, title: str, artist: str = "Stray Kids") -> dict | None:
        """Search Spotify for a track and return the first result, or None."""
        params = {"q": f"track:{title} artist:{artist}", "type": "track", "limit": 1}
        response = requests.get(SPOTIFY_SEARCH_URL, headers=self._headers(), params=params)
        response.raise_for_status()
        items = response.json().get("tracks", {}).get("items", [])
        return items[0] if items else None

    def enrich_songs(self, db: Session) -> None:
        """
        For every Song without a spotify_id, search Spotify and fill in
        duration_seconds, spotify_id, and isrc.
        """
        # TODO: implement in Phase 5
        raise NotImplementedError
