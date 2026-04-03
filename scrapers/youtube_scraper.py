"""
Phase 6 scraper: YouTube Data API v3 — find official MVs for songs.

Strategy (filtered-first to stay within the free 10,000 unit/day quota):

  Pass 1 — Search only for title tracks on main release types
            (studio_album, ep, single_album, repackage, mixtape,
            compilation_album, digital_single), excluding instrumentals
            and covers. Typically 40–60 searches (~4,000–6,000 units).

  Pass 2 — Fallback: search for any remaining released songs still
            missing a youtube_url, excluding instrumentals. Runs until
            all songs are enriched or the daily quota is exhausted.
            Re-running the next day resumes where it left off.

Each search costs 100 units. Free quota: 10,000 units/day = 100 searches.
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

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

PASS1_RELEASE_TYPES = {
    "studio_album", "ep", "single_album", "compilation_album",
    "repackage", "mixtape", "digital_single",
}


class QuotaExceeded(Exception):
    """Raised when the YouTube API daily quota is exhausted."""
    pass


class YouTubeScraper:

    def __init__(self):
        self.api_key = os.environ["YOUTUBE_API_KEY"]

    # -----------------------------------------------------------------------
    # API
    # -----------------------------------------------------------------------

    def _search(self, query: str) -> str | None:
        """
        Search YouTube for query, return the URL of the first video result.
        Returns None if no results. Raises QuotaExceeded on quota error.
        """
        time.sleep(0.3)
        response = requests.get(YOUTUBE_SEARCH_URL, params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "key": self.api_key,
        })

        if response.status_code == 403:
            data = response.json()
            errors = data.get("error", {}).get("errors", [])
            if any(e.get("reason") == "quotaExceeded" for e in errors):
                raise QuotaExceeded("YouTube API daily quota exhausted. Run again tomorrow.")
            response.raise_for_status()

        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return None
        video_id = items[0]["id"]["videoId"]
        return f"https://www.youtube.com/watch?v={video_id}"

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def enrich_songs(self, db: Session) -> None:
        """
        Run Pass 1 then Pass 2. If the daily quota is hit, commits progress
        and exits cleanly. Re-running the next day picks up where it left off.
        """
        try:
            self._pass1_title_tracks(db)
            self._pass2_fallback(db)
        except QuotaExceeded as e:
            db.commit()
            logger.error(f"\nRun aborted: {e}")
            logger.error("Progress saved. Run again tomorrow to continue.")

    # -----------------------------------------------------------------------
    # Pass 1: title tracks on main releases
    # -----------------------------------------------------------------------

    def _pass1_title_tracks(self, db: Session) -> None:
        logger.info("Pass 1: Searching YouTube for title track MVs...")

        songs = (
            db.query(Song)
            .join(Track, Track.song_id == Song.id)
            .join(Release, Release.id == Track.release_id)
            .filter(
                Track.is_title_track == True,
                Release.release_type.in_(PASS1_RELEASE_TYPES),
                Song.youtube_url.is_(None),
                Song.is_instrumental == False,
                Song.original_artist.is_(None),
            )
            .distinct()
            .order_by(Song.id)
            .all()
        )

        logger.info(f"  {len(songs)} title tracks need YouTube enrichment")
        found = 0
        not_found = 0

        for song in songs:
            query = f'Stray Kids "{song.title}" MV official'
            url = self._search(query)
            if url:
                song.youtube_url = url
                db.commit()
                found += 1
                logger.info(f"  Found: {song.title} → {url}")
            else:
                not_found += 1
                logger.debug(f"  Not found: {song.title}")

        logger.info(f"Pass 1 complete. Found: {found} | Not found: {not_found}")

    # -----------------------------------------------------------------------
    # Pass 2: fallback for remaining songs
    # -----------------------------------------------------------------------

    def _pass2_fallback(self, db: Session) -> None:
        logger.info("Pass 2: Fallback search for remaining songs...")

        songs = (
            db.query(Song)
            .filter(
                Song.youtube_url.is_(None),
                Song.is_instrumental == False,
                Song.release_status == "released",
                Song.parent_song_id.is_(None),  # skip version songs
            )
            .order_by(Song.id)
            .all()
        )

        logger.info(f"  {len(songs)} songs still need YouTube enrichment")
        found = 0
        not_found = 0

        for song in songs:
            query = f'Stray Kids "{song.title}" MV official'
            url = self._search(query)
            if url:
                song.youtube_url = url
                db.commit()
                found += 1
                logger.info(f"  Found: {song.title} → {url}")
            else:
                not_found += 1
                logger.debug(f"  Not found: {song.title}")

        logger.info(f"Pass 2 complete. Found: {found} | Not found: {not_found}")
