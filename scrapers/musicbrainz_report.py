"""
MusicBrainz gap report — standalone, NOT part of the main pipeline.

Compares our local song database against MusicBrainz's Stray Kids recording
catalogue to identify where our Spotify IDs could be contributed to MB.

Run with:
  poetry run python -m scrapers.musicbrainz_report

Output:
  data/musicbrainz_gap_report.md  — human-readable report
  data/musicbrainz_gap_report.json — machine-readable (same data)

Three categories of findings:

  MISSING_SPOTIFY_URL
    MB has a Recording for this song but it has no Spotify URL relationship.
    Our spotify_id could be added directly to MB.

  NO_MB_RECORDING
    We have a song with a spotify_id but no matching Recording was found in MB.
    Either MB doesn't have the recording at all, or the title match failed.

  ALREADY_LINKED
    MB Recording already has a Spotify URL and it matches ours.
    Informational only — nothing to do.
"""
import json
import logging
import re
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.songs import Song
from scrapers.musicbrainz_scraper import MusicBrainzScraper, CACHE_DIR

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MB_BASE_URL = "https://musicbrainz.org/ws/2"
MB_ARTIST_ENDPOINT = f"{MB_BASE_URL}/artist"
MB_RECORDING_BROWSE_ENDPOINT = f"{MB_BASE_URL}/recording"

# Stray Kids' MusicBrainz artist MBID
SKZ_ARTIST_MBID = "142b343d-bf5a-428c-a64f-6d1a7566bbe9"

# Duration match tolerance in seconds
DURATION_TOLERANCE = 5

OUTPUT_DIR = Path("data")


def normalize(title: str) -> str:
    """Lowercase, strip punctuation and extra whitespace for fuzzy title matching."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


class MusicBrainzReportScraper(MusicBrainzScraper):
    """Extends the base scraper with browse and report-specific methods."""

    def get_all_recordings(self) -> list[dict]:
        """
        Browse all Recordings attributed to SKZ on MusicBrainz.
        Uses offset pagination (100 per page) and caches the full list.
        Includes URL relationships so we can see which already have Spotify links.
        """
        cache_key = f"browse_recordings_{SKZ_ARTIST_MBID}"
        cached = self._cache_load(cache_key)
        if cached is not None:
            logger.info(f"  Loaded {len(cached)} recordings from cache")
            return cached

        recordings = []
        offset = 0
        limit = 100

        while True:
            logger.info(f"  Fetching recordings {offset}–{offset + limit}...")
            data = self._get(MB_RECORDING_BROWSE_ENDPOINT, params={
                "artist": SKZ_ARTIST_MBID,
                "inc": "url-rels",
                "limit": limit,
                "offset": offset,
            })
            batch = data.get("recordings", [])
            recordings.extend(batch)

            total = data.get("recording-count", 0)
            offset += len(batch)
            if offset >= total or not batch:
                break

        logger.info(f"  Total MB recordings fetched: {len(recordings)}")
        self._cache_save(cache_key, recordings)
        return recordings

    def build_mb_index(self, recordings: list[dict]) -> dict:
        """
        Build a normalised-title → list[recording] index from MB recordings.
        Also extracts any existing Spotify track IDs from URL relationships.
        """
        index: dict[str, list[dict]] = {}
        for rec in recordings:
            # Extract Spotify track ID from url-rels if present
            spotify_id = None
            for rel in rec.get("relations", []):
                url = rel.get("url", {}).get("resource", "")
                if "open.spotify.com/track/" in url:
                    spotify_id = url.split("/track/")[-1].split("?")[0]
                    break
            rec["_spotify_id"] = spotify_id

            key = normalize(rec["title"])
            index.setdefault(key, []).append(rec)

        return index

    def match_recording(
        self, song: Song, mb_index: dict
    ) -> tuple[dict | None, str]:
        """
        Try to match a local song to a MB Recording.

        Returns (recording, match_quality) where match_quality is one of:
          'exact'    — title + duration within tolerance
          'title'    — title only (duration unknown or outside tolerance)
          None       — no match
        """
        key = normalize(song.title)
        candidates = mb_index.get(key, [])

        if not candidates:
            return None, "none"

        # If duration is available, prefer candidates within tolerance
        if song.duration_seconds:
            for rec in candidates:
                mb_duration = rec.get("length")  # MB stores duration in ms
                if mb_duration:
                    mb_seconds = mb_duration / 1000
                    if abs(mb_seconds - song.duration_seconds) <= DURATION_TOLERANCE:
                        return rec, "exact"

        # Fall back to title-only match (first candidate)
        return candidates[0], "title"


def generate_report(db: Session, scraper: MusicBrainzReportScraper) -> dict:
    logger.info("Fetching all SKZ recordings from MusicBrainz...")
    recordings = scraper.get_all_recordings()
    mb_index = scraper.build_mb_index(recordings)

    logger.info(f"  MB index built: {len(mb_index)} unique normalised titles")

    # Songs that have a spotify_id — these are candidates to contribute
    songs = (
        db.query(Song)
        .filter(Song.spotify_id.isnot(None))
        .order_by(Song.title)
        .all()
    )

    missing_spotify_url = []   # MB has recording, missing Spotify link
    no_mb_recording = []       # We couldn't find a matching MB recording
    already_linked = []        # MB already has correct Spotify link
    mismatch = []              # MB has a Spotify link but it differs from ours

    for song in songs:
        rec, quality = scraper.match_recording(song, mb_index)

        if rec is None:
            no_mb_recording.append({
                "title": song.title,
                "our_spotify_id": song.spotify_id,
                "our_spotify_url": f"https://open.spotify.com/track/{song.spotify_id}",
                "our_isrc": song.isrc,
                "duration_seconds": song.duration_seconds,
            })
            continue

        mb_spotify_id = rec.get("_spotify_id")
        mb_url = f"https://musicbrainz.org/recording/{rec['id']}"

        if mb_spotify_id is None:
            missing_spotify_url.append({
                "title": song.title,
                "match_quality": quality,
                "mb_recording_id": rec["id"],
                "mb_recording_url": mb_url,
                "our_spotify_id": song.spotify_id,
                "our_spotify_url": f"https://open.spotify.com/track/{song.spotify_id}",
                "our_isrc": song.isrc,
                "duration_seconds": song.duration_seconds,
            })
        elif mb_spotify_id == song.spotify_id:
            already_linked.append({
                "title": song.title,
                "mb_recording_id": rec["id"],
                "spotify_id": song.spotify_id,
            })
        else:
            mismatch.append({
                "title": song.title,
                "match_quality": quality,
                "mb_recording_id": rec["id"],
                "mb_recording_url": mb_url,
                "mb_spotify_id": mb_spotify_id,
                "mb_spotify_url": f"https://open.spotify.com/track/{mb_spotify_id}",
                "our_spotify_id": song.spotify_id,
                "our_spotify_url": f"https://open.spotify.com/track/{song.spotify_id}",
            })

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mb_recordings_total": len(recordings),
        "our_songs_with_spotify": len(songs),
        "missing_spotify_url": missing_spotify_url,
        "no_mb_recording": no_mb_recording,
        "already_linked": already_linked,
        "mismatch": mismatch,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# MusicBrainz Gap Report",
        f"",
        f"Generated: {report['generated_at']}",
        f"",
        f"| Category | Count |",
        f"|---|---|",
        f"| MB recordings fetched | {report['mb_recordings_total']} |",
        f"| Our songs with Spotify ID | {report['our_songs_with_spotify']} |",
        f"| **Missing Spotify URL on MB** | **{len(report['missing_spotify_url'])}** |",
        f"| Already linked correctly | {len(report['already_linked'])} |",
        f"| No MB recording found | {len(report['no_mb_recording'])} |",
        f"| Spotify ID mismatch | {len(report['mismatch'])} |",
        f"",
    ]

    if report["missing_spotify_url"]:
        lines += [
            "## Missing Spotify URL on MusicBrainz",
            "",
            "MB has a Recording for these songs but no Spotify URL relationship. "
            "These are the best candidates to contribute.",
            "",
            "| Song | Match | MB Recording | Spotify URL |",
            "|---|---|---|---|",
        ]
        for item in sorted(report["missing_spotify_url"], key=lambda x: x["title"]):
            lines.append(
                f"| {item['title']} | {item['match_quality']} "
                f"| [Recording]({item['mb_recording_url']}) "
                f"| [Spotify]({item['our_spotify_url']}) |"
            )
        lines.append("")

    if report["mismatch"]:
        lines += [
            "## Spotify ID Mismatch",
            "",
            "MB has a Spotify link, but it differs from ours. Worth investigating manually.",
            "",
            "| Song | MB Recording | MB Spotify | Our Spotify |",
            "|---|---|---|---|",
        ]
        for item in sorted(report["mismatch"], key=lambda x: x["title"]):
            lines.append(
                f"| {item['title']} "
                f"| [Recording]({item['mb_recording_url']}) "
                f"| [MB Spotify]({item['mb_spotify_url']}) "
                f"| [Our Spotify]({item['our_spotify_url']}) |"
            )
        lines.append("")

    if report["no_mb_recording"]:
        lines += [
            "## No MB Recording Found",
            "",
            "We have a Spotify ID for these songs but couldn't match them to a MB Recording. "
            "MB may not have these recordings, or the title match failed.",
            "",
            "| Song | Spotify URL |",
            "|---|---|",
        ]
        for item in sorted(report["no_mb_recording"], key=lambda x: x["title"]):
            lines.append(f"| {item['title']} | [Spotify]({item['our_spotify_url']}) |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    db = SessionLocal()
    try:
        scraper = MusicBrainzReportScraper(use_cache=True)
        report = generate_report(db, scraper)

        OUTPUT_DIR.mkdir(exist_ok=True)
        json_path = OUTPUT_DIR / "musicbrainz_gap_report.json"
        md_path = OUTPUT_DIR / "musicbrainz_gap_report.md"

        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        write_markdown(report, md_path)

        logger.info("")
        logger.info(f"Report written to:")
        logger.info(f"  {md_path}")
        logger.info(f"  {json_path}")
        logger.info("")
        logger.info(f"  Missing Spotify URL on MB : {len(report['missing_spotify_url'])}")
        logger.info(f"  Already linked correctly  : {len(report['already_linked'])}")
        logger.info(f"  No MB recording found     : {len(report['no_mb_recording'])}")
        logger.info(f"  Spotify ID mismatch       : {len(report['mismatch'])}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
