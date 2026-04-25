"""
Phase 7 scraper: MusicBrainz — ISRC and Recording MBID enrichment.

Strategy (two-call lookup per song via Spotify URL relationships):

  For each song that has a spotify_id but no isrc or musicbrainz_id:

    Call 1 — GET /ws/2/url?resource=https://open.spotify.com/track/{spotify_id}
              Returns the URL entity and its linked Recording via relations.
              Extracts the Recording MBID.

    Call 2 — GET /ws/2/recording/{mbid}?inc=isrcs
              Returns ISRCs attached to that Recording.

  Sets: musicbrainz_id (always when found), isrc (only if not already set).

Rate limit: 1 req/sec average. MusicBrainz returns 503 (not 429) on
violation. The scraper sleeps 1 second between every call and retries
once on 503 with an additional 5-second back-off.

No API key required. A descriptive User-Agent with contact info is
mandatory — requests without one are deprioritised or blocked.
Set MUSICBRAINZ_CONTACT in .env to your email address.

All responses are cached to disk indefinitely (MusicBrainz data is CC0).
The cache is intentionally not TTL-limited here since Recording/ISRC
relationships don't change.

Coverage gap: not every Spotify track has a URL relationship in
MusicBrainz. Songs with no MB match are skipped silently — they keep
their spotify_id and will remain without isrc.
"""
import json
import os
import time
import logging
import hashlib
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models.songs import Song

load_dotenv()

logger = logging.getLogger(__name__)

MB_BASE_URL = "https://musicbrainz.org/ws/2"
MB_URL_ENDPOINT = f"{MB_BASE_URL}/url"
MB_RECORDING_ENDPOINT = f"{MB_BASE_URL}/recording"

# Sleep between every request to stay within the 1 req/sec average
_REQUEST_INTERVAL = 1.1

# On 503, back off this many seconds before one retry
_BACKOFF_SECONDS = 5

CACHE_DIR = Path("data/musicbrainz_cache")


class MusicBrainzScraper:

    def __init__(self, use_cache: bool = True):
        contact = os.environ.get("MUSICBRAINZ_CONTACT", "")
        if not contact:
            raise ValueError(
                "MUSICBRAINZ_CONTACT is not set. MusicBrainz requires a contact "
                "email in the User-Agent header. Set it in your .env file."
            )
        self._headers = {
            "User-Agent": f"skz-database/1.0 ( {contact} )",
            "Accept": "application/json",
        }
        self._use_cache = use_cache
        self._last_call: float = 0.0

    # -----------------------------------------------------------------------
    # HTTP
    # -----------------------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < _REQUEST_INTERVAL:
            time.sleep(_REQUEST_INTERVAL - elapsed)

    def _get(self, url: str, params: dict) -> dict:
        self._throttle()
        params = {**params, "fmt": "json"}

        for attempt in range(2):
            try:
                response = requests.get(url, params=params, headers=self._headers, timeout=30)
                self._last_call = time.monotonic()
            except requests.exceptions.Timeout:
                if attempt == 0:
                    logger.warning(f"  Timeout — backing off {_BACKOFF_SECONDS}s and retrying")
                    time.sleep(_BACKOFF_SECONDS)
                    continue
                logger.warning(f"  Timeout on retry — skipping")
                return {}

            if response.status_code == 503:
                if attempt == 0:
                    logger.warning(f"  503 from MusicBrainz — backing off {_BACKOFF_SECONDS}s and retrying")
                    time.sleep(_BACKOFF_SECONDS)
                    continue
                logger.warning(f"  503 on retry — skipping")
                return {}

            if response.status_code == 404:
                return {}

            response.raise_for_status()
            return response.json()

        return {}

    # -----------------------------------------------------------------------
    # Disk cache
    # -----------------------------------------------------------------------

    def _cache_load(self, key: str) -> dict | None:
        """Return cached value, or None if not cached. Empty dict {} means a cached miss."""
        if not self._use_cache:
            return None
        path = CACHE_DIR / f"{key}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def _cache_save(self, key: str, data: dict) -> None:
        if not self._use_cache:
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_DIR / f"{key}.json", "w") as f:
            json.dump(data, f)

    # -----------------------------------------------------------------------
    # Lookups
    # -----------------------------------------------------------------------

    def get_recording_mbid(self, spotify_id: str) -> str | None:
        """
        Call 1: Resolve a Spotify track ID to a MusicBrainz Recording MBID.

        Uses the MusicBrainz URL entity endpoint — looks up the URL entity for
        the Spotify track URL and extracts the linked Recording relationship.
        Returns None if no MB recording is linked to this Spotify track.
        """
        cache_key = f"url_{spotify_id}"
        cached = self._cache_load(cache_key)
        if cached is not None:
            return cached.get("mbid") or None

        resource = f"https://open.spotify.com/track/{spotify_id}"
        data = self._get(MB_URL_ENDPOINT, params={"resource": resource, "inc": "recording-rels"})

        if not data:
            self._cache_save(cache_key, {})
            return None

        # The URL entity response includes a `relations` list. Each relation has a
        # `target-type` field; for recording links, the Recording is in `recording`.
        mbid = None
        for rel in data.get("relations", []):
            if rel.get("target-type") == "recording":
                mbid = rel["recording"]["id"]
                break

        self._cache_save(cache_key, {"mbid": mbid} if mbid else {})
        return mbid

    def get_isrcs(self, mbid: str) -> list[str]:
        """
        Call 2: Fetch ISRCs for a Recording MBID.

        Returns a list of ISRCs (usually 1, occasionally more for re-releases).
        Returns an empty list if none are attached.
        """
        cache_key = f"recording_{mbid}"
        cached = self._cache_load(cache_key)
        if cached is not None:
            return cached.get("isrcs", [])

        data = self._get(MB_RECORDING_ENDPOINT + f"/{mbid}", params={"inc": "isrcs"})

        if not data:
            self._cache_save(cache_key, {"isrcs": []})
            return []

        isrcs = data.get("isrcs", [])
        self._cache_save(cache_key, {"isrcs": isrcs})
        return isrcs

    # -----------------------------------------------------------------------
    # Main enrichment pass
    # -----------------------------------------------------------------------

    def enrich_songs(self, db: Session) -> None:
        """
        Enrich songs that have a spotify_id but no musicbrainz_id or isrc.

        Songs already enriched by a previous run are skipped (idempotent).
        """
        songs = (
            db.query(Song)
            .filter(
                Song.spotify_id.isnot(None),
                Song.musicbrainz_id.is_(None),
            )
            .order_by(Song.id)
            .all()
        )

        if not songs:
            logger.info("MusicBrainz: All songs already have a Recording MBID — skipping.")
            return

        logger.info(f"MusicBrainz: {len(songs)} songs to look up...")

        enriched_mbid = 0
        enriched_isrc = 0
        not_found = 0

        for song in songs:
            mbid = self.get_recording_mbid(song.spotify_id)
            if not mbid:
                not_found += 1
                logger.debug(f"  No MB recording found: {song.title}")
                continue

            song.musicbrainz_id = mbid
            enriched_mbid += 1

            if song.isrc is None:
                isrcs = self.get_isrcs(mbid)
                if isrcs:
                    song.isrc = isrcs[0]
                    enriched_isrc += 1
                    logger.info(f"  Enriched: {song.title} → mbid={mbid} isrc={isrcs[0]}")
                else:
                    logger.info(f"  MBID set, no ISRC: {song.title} → mbid={mbid}")
            else:
                logger.info(f"  MBID set (ISRC already present): {song.title} → mbid={mbid}")

            db.commit()

        logger.info(
            f"MusicBrainz complete. "
            f"MBIDs set: {enriched_mbid} | ISRCs set: {enriched_isrc} | Not found: {not_found}"
        )
