"""
Phase 5 scraper: Spotify Web API enrichment via Client Credentials flow.

Strategy (album-first to minimise API calls and avoid rate limiting):

  Pass 1 — Fetch all Stray Kids albums from Spotify's artist endpoint.
            For each album, fetch the full tracklist. Match each Spotify
            track to an existing Song by title (exact then case-insensitive).
            Sets: spotify_id, duration_seconds, isrc, track_number on Track.
            Creates new Song + Track rows for any tracks not already in DB.

  Pass 2 — For any Song still without a spotify_id after Pass 1
            (covers, SKZ-Record, etc.), fall back to individual track search.
            This is a small set so rate limiting is not a concern.

Total API calls: ~3 (artist albums) + ~30 (tracklists) + handful of fallbacks
vs. the old approach of ~300 individual searches.

Does NOT require user login — uses Client ID + Secret only.
"""
import os
import time
import logging

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models.releases import Release
from app.models.songs import Song, Track

load_dotenv()

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when Spotify asks us to wait longer than MAX_RETRY_WAIT_SECONDS."""
    pass

SPOTIFY_TOKEN_URL   = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL  = "https://api.spotify.com/v1/search"
SPOTIFY_ARTIST_URL  = "https://api.spotify.com/v1/artists"
SPOTIFY_ALBUM_URL   = "https://api.spotify.com/v1/albums"
SPOTIFY_TRACKS_URL  = "https://api.spotify.com/v1/tracks"

SKZ_ARTIST_NAME = "Stray Kids"

# Only enrich songs with these statuses
ENRICHABLE_STATUSES = {"released"}

# Release types to fill tracklists for
TRACKLIST_RELEASE_TYPES = {
    "studio_album", "ep", "compilation_album",
    "repackage", "mixtape", "single_album",
}


class SpotifyScraper:

    def __init__(self):
        self.client_id = os.environ["SPOTIFY_CLIENT_ID"]
        self.client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
        self._token: str | None = None
        self._token_expiry: float = 0

    # -----------------------------------------------------------------------
    # Auth + HTTP
    # -----------------------------------------------------------------------

    def _get_token(self) -> str:
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
        self._token_expiry = time.time() + data["expires_in"] - 60
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    # If Spotify asks us to wait longer than this, abort rather than block.
    MAX_RETRY_WAIT_SECONDS = 120

    def _get(self, url: str, params: dict = None, _retries: int = 4) -> dict:
        time.sleep(0.3)
        response = requests.get(url, headers=self._headers(), params=params)
        if response.status_code == 429 and _retries > 0:
            retry_after = int(response.headers.get("Retry-After", 15))
            if retry_after > self.MAX_RETRY_WAIT_SECONDS:
                raise RateLimitExceeded(
                    f"Spotify rate limit too long: {retry_after}s "
                    f"(max allowed: {self.MAX_RETRY_WAIT_SECONDS}s). "
                    f"Run again later."
                )
            logger.warning(f"  Rate limited — waiting {retry_after}s")
            time.sleep(retry_after)
            return self._get(url, params, _retries - 1)
        response.raise_for_status()
        return response.json()

    # -----------------------------------------------------------------------
    # Spotify data fetchers
    # -----------------------------------------------------------------------

    def get_artist_id(self) -> str:
        """Look up Stray Kids' Spotify artist ID dynamically."""
        data = self._get(SPOTIFY_SEARCH_URL, params={
            "q": f"artist:{SKZ_ARTIST_NAME}",
            "type": "artist",
            "limit": 10,
            "market": "US",
        })
        items = data.get("artists", {}).get("items", [])
        # Find the artist whose name matches exactly (case-insensitive)
        for item in items:
            if item["name"].lower() == SKZ_ARTIST_NAME.lower():
                logger.info(f"  Stray Kids Spotify artist ID: {item['id']}")
                return item["id"]
        raise RuntimeError(
            f"Could not find an artist named '{SKZ_ARTIST_NAME}' in Spotify search results. "
            f"Got: {[i['name'] for i in items]}"
        )

    def get_artist_albums(self) -> list[dict]:
        """Fetch all albums/EPs/singles for Stray Kids from Spotify."""
        artist_id = self.get_artist_id()
        albums = []
        url = f"{SPOTIFY_ARTIST_URL}/{artist_id}/albums"
        params = {"limit": 50, "include_groups": "album,single,compilation", "market": "US"}
        while url:
            data = self._get(url, params=params)
            albums.extend(data.get("items", []))
            url = data.get("next")
            params = {}
        return albums

    def get_album_tracks(self, spotify_album_id: str) -> list[dict]:
        """Fetch all tracks for a Spotify album, handling pagination."""
        tracks = []
        url = f"{SPOTIFY_ALBUM_URL}/{spotify_album_id}/tracks"
        params = {"limit": 50, "market": "US"}
        while url:
            data = self._get(url, params=params)
            tracks.extend(data.get("items", []))
            url = data.get("next")
            params = {}
        return tracks

    def get_tracks_batch(self, track_ids: list[str]) -> list[dict]:
        """
        Fetch full track details (including ISRC) for up to 50 track IDs at once.
        Much more efficient than fetching one at a time.
        """
        results = []
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i:i + 50]
            data = self._get(SPOTIFY_TRACKS_URL, params={"ids": ",".join(batch), "market": "US"})
            results.extend(data.get("tracks", []))
        return results

    def search_track(self, title: str, artist: str = "Stray Kids") -> dict | None:
        """Fallback: search for a single track by title."""
        data = self._get(SPOTIFY_SEARCH_URL, params={
            "q": f"track:{title} artist:{artist}",
            "type": "track",
            "limit": 1,
            "market": "US",
        })
        items = data.get("tracks", {}).get("items", [])
        return items[0] if items else None

    # -----------------------------------------------------------------------
    # Song matching helpers
    # -----------------------------------------------------------------------

    def _find_song(self, db: Session, title: str, spotify_id: str) -> Song | None:
        """Find an existing song by spotify_id, exact title, or case-insensitive title."""
        return (
            db.query(Song).filter(Song.spotify_id == spotify_id).first()
            or db.query(Song).filter(Song.title == title).first()
            or db.query(Song).filter(Song.title.ilike(title)).first()
        )

    def _safe_set_isrc(self, db: Session, song: Song, isrc: str) -> None:
        """Set ISRC only if no other song already holds it."""
        if not isrc:
            return
        conflict = db.query(Song).filter(
            Song.isrc == isrc, Song.id != song.id
        ).first()
        if not conflict:
            song.isrc = isrc

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def enrich_songs(self, db: Session) -> None:
        """
        Phase 5.0: Discover releases on Spotify not yet in our DB.
        Pass 1:    Album-first traversal — covers all officially released songs
                   in ~30 API calls total.
        Pass 2:    Fallback individual search for anything Pass 1 missed
                   (SKZ-Record covers, unreleased that somehow slipped through, etc.)

        If Spotify rate-limits us with a wait longer than MAX_RETRY_WAIT_SECONDS,
        the run is aborted cleanly. Progress already committed is preserved —
        re-running will skip already-enriched songs and pick up where it left off.
        """
        try:
            self._discover_missing_releases(db)
            self._album_first_enrichment(db)
            self._fallback_search_enrichment(db)
        except RateLimitExceeded as e:
            db.commit()  # Save whatever progress was made before the limit hit
            logger.error(f"\nRun aborted: {e}")
            logger.error("Progress has been saved. Run again once the rate limit clears.")

    # -----------------------------------------------------------------------
    # Phase 5.0: Release discovery
    # -----------------------------------------------------------------------

    # Map Spotify album_type + track count → our release_type
    _SPOTIFY_TYPE_MAP = {
        "album": "studio_album",
        "single": "digital_single",
        "compilation": "compilation_album",
    }

    def _discover_missing_releases(self, db: Session) -> None:
        """
        Fetch all Stray Kids releases from Spotify's artist/albums endpoint and
        insert any that aren't already in our releases table.

        This catches releases missing from the main Wikipedia discography page —
        such as remix EPs, collab singles, or bonus editions — so that the
        album-first enrichment pass can populate their tracks.
        """
        import re
        from datetime import date

        logger.info("Phase 5.0: Discovering releases missing from the database...")

        sp_albums = self.get_artist_albums()

        # Build normalised title → id map of what we already have
        existing = {r.title.lower().strip(): r.id for r in db.query(Release).all()}

        new_count = 0
        for sp_album in sp_albums:
            title = sp_album["name"]
            key = title.lower().strip()

            if key in existing:
                continue

            # Map Spotify album_type to our release_type
            sp_type = sp_album.get("album_type", "single")
            release_type = self._SPOTIFY_TYPE_MAP.get(sp_type, "digital_single")

            # Parse release_date — Spotify provides precision alongside the date string
            raw_date = sp_album.get("release_date", "")
            precision = sp_album.get("release_date_precision", "day")
            parsed_date = None
            try:
                if precision == "day":
                    parsed_date = date.fromisoformat(raw_date)
                elif precision == "month":
                    y, m = raw_date.split("-")[:2]
                    parsed_date = date(int(y), int(m), 1)
                elif precision == "year":
                    parsed_date = date(int(raw_date), 1, 1)
            except (ValueError, TypeError):
                pass

            release = Release(
                title=title,
                release_type=release_type,
                release_date=parsed_date,
                release_date_precision=precision,
                market="GLOBAL",
                source="spotify",
                is_verified=True,
            )
            db.add(release)
            db.flush()
            existing[key] = release.id
            logger.info(f"  New release: {title} ({release_type}, {raw_date or 'no date'})")
            new_count += 1

        db.commit()
        logger.info(f"Phase 5.0 complete. {new_count} new release(s) added.")

    # -----------------------------------------------------------------------
    # Pass 1: Album-first
    # -----------------------------------------------------------------------

    def _album_first_enrichment(self, db: Session) -> None:
        logger.info("Pass 1: Album-first enrichment from Spotify artist catalogue...")

        sp_albums = self.get_artist_albums()
        logger.info(f"  Found {len(sp_albums)} releases on Spotify for Stray Kids")

        # Build a map of normalised album title → our Release id for linking tracks
        our_releases = db.query(Release).filter(
            Release.release_type.in_(TRACKLIST_RELEASE_TYPES)
        ).all()
        release_map: dict[str, int] = {}
        for r in our_releases:
            release_map[r.title.lower().strip()] = r.id

        enriched_songs = 0
        new_songs = 0

        for sp_album in sp_albums:
            album_title = sp_album["name"]
            sp_album_id = sp_album["id"]

            sp_tracks = self.get_album_tracks(sp_album_id)
            if not sp_tracks:
                continue

            # Fetch full track details in one batch call to get ISRCs
            track_ids = [t["id"] for t in sp_tracks if t.get("id")]
            full_tracks = {t["id"]: t for t in self.get_tracks_batch(track_ids) if t}

            logger.info(f"  Processing album: {album_title} ({len(sp_tracks)} tracks)")

            # Find matching release in our DB
            our_release_id = release_map.get(album_title.lower().strip())

            for i, sp_track in enumerate(sp_tracks, start=1):
                sp_id = sp_track.get("id")
                if not sp_id:
                    continue
                title = sp_track["name"]
                duration_s = sp_track["duration_ms"] // 1000
                full = full_tracks.get(sp_id, {})
                isrc = full.get("external_ids", {}).get("isrc")

                song = self._find_song(db, title, sp_id)

                if song:
                    # Enrich existing song
                    if song.spotify_id is None:
                        song.spotify_id = sp_id
                    if song.duration_seconds is None:
                        song.duration_seconds = duration_s
                    self._safe_set_isrc(db, song, isrc)
                    enriched_songs += 1
                else:
                    # Create new song from Spotify data
                    song = Song(
                        title=title,
                        duration_seconds=duration_s,
                        spotify_id=sp_id,
                        language="ko",
                        release_status="released",
                        is_verified=True,
                        source="spotify",
                    )
                    self._safe_set_isrc(db, song, isrc)
                    db.add(song)
                    db.flush()
                    new_songs += 1
                    logger.info(f"    New song: {title}")

                # Link to our release if we have one and track isn't already linked
                if our_release_id:
                    exists = db.query(Track).filter(
                        Track.release_id == our_release_id,
                        Track.song_id == song.id,
                    ).first()
                    if not exists:
                        db.add(Track(
                            release_id=our_release_id,
                            song_id=song.id,
                            track_number=i,
                            disc_number=sp_track.get("disc_number", 1),
                        ))

            db.commit()

        logger.info(f"Pass 1 complete. Enriched: {enriched_songs} | New songs added: {new_songs}")

    # -----------------------------------------------------------------------
    # Pass 2: Fallback individual search
    # -----------------------------------------------------------------------

    def _fallback_search_enrichment(self, db: Session) -> None:
        logger.info("Pass 2: Fallback search for remaining unenriched songs...")

        songs = (
            db.query(Song)
            .filter(
                Song.spotify_id.is_(None),
                Song.release_status.in_(ENRICHABLE_STATUSES),
            )
            .all()
        )
        logger.info(f"  {len(songs)} songs still need enrichment")

        enriched = 0
        not_found = 0

        for song in songs:
            result = self.search_track(song.title)
            if not result:
                not_found += 1
                logger.debug(f"  Not found: {song.title}")
                continue

            song.spotify_id = result["id"]
            song.duration_seconds = result["duration_ms"] // 1000
            isrc = result.get("external_ids", {}).get("isrc")
            self._safe_set_isrc(db, song, isrc)

            try:
                db.commit()
                enriched += 1
                logger.info(f"  Enriched: {song.title} ({song.duration_seconds}s)")
            except Exception:
                db.rollback()
                song.isrc = None
                try:
                    db.commit()
                    enriched += 1
                    logger.warning(f"  ISRC conflict skipped for: {song.title}")
                except Exception:
                    db.rollback()
                    not_found += 1
                    logger.warning(f"  Skipped: {song.title}")

        logger.info(f"Pass 2 complete. Enriched: {enriched} | Not found: {not_found}")
