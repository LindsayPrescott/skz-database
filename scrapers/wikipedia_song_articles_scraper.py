"""
Phase 2.6: Wikipedia individual song article scraper.

For songs that have a dedicated Wikipedia article link stored in fandom_url,
this scraper fetches the article and parses the ==Track listing== section to:
  - Discover releases that don't appear in the main discography table
    (e.g. remix EPs like Ceremony's "Maximum Power Remixes")
  - Create Song version rows (parent_song_id) for each listed variant
  - Link those version songs to their releases via Track rows

This runs after Phase 2 and before Phase 4 (dedup) so versions are in place
before Spotify enrichment runs.
"""
import re
import time
import logging
from urllib.parse import unquote

import requests
from sqlalchemy.orm import Session

from app.models.releases import Release
from app.models.songs import Song
from scrapers.utils import find_song, find_release, link_song_to_release

logger = logging.getLogger(__name__)

MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"


class WikipediaSongArticlesScraper:

    def scrape_song_articles(self, db: Session) -> None:
        """
        Query all songs with a Wikipedia article link and parse their track listings.
        Songs scraped from the Wikipedia songs list store the article URL in wikipedia_url.
        """
        songs = (
            db.query(Song)
            .filter(Song.wikipedia_url.like("https://en.wikipedia.org/wiki/%"))
            .all()
        )
        logger.info(f"  {len(songs)} songs have Wikipedia article links — checking track listings")

        processed = 0
        for song in songs:
            # URL-decode the page name so "Why%3F_..." becomes "Why?_..." before API call
            page_name = unquote(song.wikipedia_url.split("/wiki/")[-1])
            try:
                found = self._process_song_article(db, song, page_name)
                if found:
                    processed += 1
            except Exception as e:
                logger.warning(f"  Skipped {song.title}: {e}")

        logger.info(f"  Articles with track listings: {processed}")

    # ---------------------------------------------------------------------------
    # Article fetching + section extraction
    # ---------------------------------------------------------------------------

    def _fetch_wikitext(self, page_name: str) -> str | None:
        time.sleep(1)  # Be polite to Wikipedia's API
        resp = requests.get(
            MEDIAWIKI_API,
            params={
                "action": "parse",
                "page": page_name,
                "prop": "wikitext",
                "format": "json",
            },
            headers={"User-Agent": "SKZDatabase/1.0 (educational music database)"},
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"    Wikipedia API returned {resp.status_code} for: {page_name}")
            return None
        if not resp.text.strip():
            logger.warning(f"    Wikipedia API returned empty body for: {page_name}")
            return None
        data = resp.json()
        if "error" in data:
            logger.warning(f"    Wikipedia API error for {page_name}: {data['error'].get('info', data['error'])}")
            return None
        if "parse" not in data:
            return None
        return data["parse"]["wikitext"]["*"]

    def _process_song_article(self, db: Session, song: Song, page_name: str) -> bool:
        """Fetch article and parse track listing. Returns True if a listing was found."""
        wikitext = self._fetch_wikitext(page_name)
        if not wikitext:
            return False

        # Extract everything under ==Track listing== up to the next L2 section (== Foo ==).
        # Use lookahead so the == marker itself isn't consumed; [^=] ensures we stop at L2
        # headers (==Foo==) but not L3 (===Foo===), and avoids the \s bug where ==Credits==
        # wasn't matching because C is not whitespace.
        match = re.search(
            r'==\s*Track\s*listing\s*==(.+?)(?=\n==[^=]|\Z)',
            wikitext,
            re.S | re.IGNORECASE,
        )
        if not match:
            return False

        logger.info(f"  Parsing track listing for: {song.title}")
        self._parse_track_listing(db, song, match.group(1))
        return True

    # ---------------------------------------------------------------------------
    # Track listing parser
    # ---------------------------------------------------------------------------

    def _parse_track_listing(self, db: Session, parent_song: Song, section: str) -> None:
        """
        Walk the track listing section line by line.

        Release headers look like:
          * '''Digital download and streaming – ''Maximum Power Remixes'''''
          * '''Standard edition'''
          ==={{nowiki}}Standard===   (rare alternate heading)

        Track entries look like:
          # "Ceremony" (Karma version) – 2:51
          # "Ceremony" (Hip Hip version; English version) – 2:38
          # "Ceremony" – 2:44          ← canonical, no version label
        """
        current_release_id: int | None = None
        track_position = 0

        for line in section.split("\n"):
            line = line.strip()
            if not line:
                continue

            # --- Release header ---
            release_title = self._extract_release_header(line)
            if release_title:
                result = self._find_or_create_release(db, release_title)
                if result is not None:
                    current_release_id = result
                track_position = 0
                continue

            # --- Track entry ---
            if line.startswith("#") and not line.startswith("##"):
                track_position += 1
                self._parse_track_entry(db, line, parent_song, current_release_id, track_position)

    def _extract_release_header(self, line: str) -> str | None:
        """
        Return the release name if this line is a release section header, else None.

        Handles:
          * '''Digital download and streaming – ''Name'''''
          * '''Name'''
        """
        if not line.startswith("*"):
            return None

        # Prefer the italic inner title: ''Release Name''
        italic = re.search(r"''([^']+)''", line)
        if italic:
            name = italic.group(1).strip()
            # Skip pure format descriptions (no letters that look like a title)
            if name and not name.lower().startswith(("digital", "physical", "cd", "streaming")):
                return name

        # Fall back to the full bold text stripped of markup
        bold = re.search(r"'{2,3}(.+?)'{2,3}", line)
        if bold:
            name = re.sub(r"'{2,3}", "", bold.group(1))
            # Strip "Digital download – " type prefixes
            if " – " in name:
                name = name.split(" – ")[-1]
            elif "—" in name:
                name = name.split("—")[-1]
            name = name.strip()
            if name:
                return name

        return None

    def _parse_track_entry(
        self,
        db: Session,
        line: str,
        parent_song: Song,
        release_id: int | None,
        track_position: int,
    ) -> None:
        """
        Parse one numbered track line and upsert the Song version + Track link.

        Formats:
          # "Title" (Hip Hip version; English version) – 2:38
          # "Title" (Karma version) – 2:51
          # "Title" – 2:44          ← no version, canonical
        """
        # Strip leading #s and whitespace
        content = re.sub(r'^#+\s*', '', line)
        # Strip wikilinks: [[Page|Display]] → Display, [[Page]] → Page
        content = re.sub(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]', r'\1', content)
        # Strip italic/bold markup: ''text'' → text
        content = re.sub(r"'{2,3}([^']*?)'{2,3}", r'\1', content)

        # Match: "Title" (optional version info) optional_duration
        m = re.match(
            r'"([^"]+)"\s*(?:\(([^)]+)\))?\s*(?:[–—-]\s*[\d:]+)?',
            content,
        )
        if not m:
            return

        raw_title = m.group(1).strip()
        version_part = m.group(2).strip() if m.group(2) else None

        # The track title may differ from the article's song (e.g. the Top article lists
        # Slump as a separate track). Look up the actual parent by title rather than
        # blindly using the article's song.
        if raw_title.lower() != parent_song.title.lower():
            actual_parent = find_song(db, raw_title)
            if actual_parent is None:
                return  # Unknown song title, skip
            effective_parent = actual_parent
        else:
            effective_parent = parent_song

        if not version_part:
            # Canonical song — link to the release if we have one, don't create a new Song
            if release_id:
                link_song_to_release(db, effective_parent, release_id, track_number=track_position)
            return

        # Parse semicolon-separated version labels: "Hip Hip version; English version"
        raw_labels = [v.strip() for v in re.split(r'[;,]', version_part)]
        # Drop "from 'Album'" context notes — they're not version labels
        raw_labels = [v for v in raw_labels if not re.match(r'^from\s+', v, re.IGNORECASE)]
        if not raw_labels:
            return  # Nothing meaningful left after filtering
        clean_labels = [
            re.sub(r'\s*ver(?:sion)?\.?\s*$', '', v, flags=re.IGNORECASE).strip()
            for v in raw_labels
        ]
        version_label = "; ".join(v for v in clean_labels if v)

        # Reconstruct full title using cleaned labels (no "from X" context noise)
        clean_version_part = "; ".join(v for v in raw_labels if v)
        full_title = f"{raw_title} ({clean_version_part})"

        # Determine language
        language = effective_parent.language or "ko"
        if any("english" in v.lower() for v in clean_labels):
            language = "en"

        song = self._find_or_create_version_song(
            db, full_title, version_label, language, effective_parent
        )
        if release_id:
            link_song_to_release(db, song, release_id, track_number=track_position)

        db.commit()

    # ---------------------------------------------------------------------------
    # DB helpers
    # ---------------------------------------------------------------------------

    # Exact titles that are format/show labels, not release names
    _SKIP_RELEASE_TITLES_EXACT = {
        "digital download", "digital download and streaming", "streaming",
        "cd", "cd single", "physical", "vinyl", "remixes",
        "inkigayo", "m countdown", "music bank", "show champion", "show! music core",
        "simply k-pop", "the show", "all the k-pop", "music core",
        "japanese version", "korean version", "english version",
        "standard edition", "limited edition", "deluxe edition",
    }

    # Prefixes that always indicate format/edition descriptions, not release names
    _SKIP_RELEASE_PREFIXES = (
        "digital download",     # "digital download (Low Steppa remix)" etc.
        "cd single",            # "cd single / digital download / streaming"
        "japanese version (",   # "japanese version (except...)"
        "korean version (",
        "english version (",
        "dvd",                  # "dvd – japanese version..."
        "blu-ray",
    )

    def _find_or_create_release(self, db: Session, title: str) -> int | None:
        key = title.lower().strip()
        if key in self._SKIP_RELEASE_TITLES_EXACT:
            return None
        if any(key.startswith(p) for p in self._SKIP_RELEASE_PREFIXES):
            return None

        existing = find_release(db, title)
        if existing:
            return existing.id

        release = Release(
            title=title,
            release_type="digital_single",
            market="GLOBAL",
            source="wikipedia",
            is_verified=True,
        )
        db.add(release)
        db.flush()
        logger.info(f"    New release discovered: {title}")
        return release.id

    def _find_or_create_version_song(
        self,
        db: Session,
        full_title: str,
        version_label: str,
        language: str,
        parent_song: Song,
    ) -> Song:
        existing = find_song(db, full_title)
        if existing:
            return existing

        # Also check by parent + version label (in case title was stored differently)
        existing = (
            db.query(Song)
            .filter(
                Song.parent_song_id == parent_song.id,
                Song.version_label.ilike(version_label),
            )
            .first()
        )
        if existing:
            return existing

        song = Song(
            title=full_title,
            parent_song_id=parent_song.id,
            version_label=version_label,
            language=language,
            release_status="released",
            is_verified=True,
            source="wikipedia",
        )
        db.add(song)
        db.flush()
        logger.info(f"    New version song: {full_title}")
        return song

