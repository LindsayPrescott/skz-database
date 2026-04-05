"""
Phase 3 scraper: Stray Kids Fandom Wiki via MediaWiki API

Pages scraped:
  - SKZ-RECORD  → release_type='skz_record', covers + original songs
  - SKZ-PLAYER  → release_type='skz_player', solo/unit personal songs
  - Other_unreleased_songs → release_status='unreleased'/'snippet'

MediaWiki API: https://stray-kids.fandom.com/api.php
"""
import re
import logging
from datetime import datetime, date

import mwparserfromhell
from sqlalchemy.orm import Session

from app.models.artists import Artist
from app.models.releases import Release
from app.models.songs import Song, Track
from app.models.credits import SongCredit
from scrapers.base_scraper import BaseScraper
from scrapers.config import GroupConfig, SKZ_CONFIG
from scrapers.utils import clean, strip_quotes, resolve_member

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_wikilinks(text: str) -> str:
    """Convert [[Target|Label]] → Label, [[Target]] → Target.
    Also strips any remaining [[ or ]] that weren't part of a valid wikilink."""
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[|\]\]", "", text)  # Remove unparsed brackets
    return text


def parse_fandom_date(text: str) -> date | None:
    """Parse dates like 'May 4, 2020' or 'Aug. 26, 2018' or 'Jul. 3, 2019'."""
    text = clean(text).strip()
    # Normalise abbreviated months: "Aug." → "Aug", "Sept." → "Sep"
    text = re.sub(r"(\w+)\.", r"\1", text).strip()
    for fmt in ("%B %d %Y", "%b %d %Y", "%B %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def extract_member_from_title(title: str, aliases: dict[str, int]) -> tuple[str, int | None]:
    """
    Handles formats:
      'MemberName "Song Title"'
      'Member1, Member2 "Song Title"'
      'MemberName [[Song Title]]'
    Returns (song_title, artist_id) or (original_title, None) if no member found.
    """
    # Pattern: one or more names (possibly comma-separated) followed by quoted title.
    # Handles both straight (U+0022) and curly (U+201C/U+201D) quote variants from
    # Fandom wikitext, and allows trailing content after the closing quote
    # (e.g. " Cover (orig. : Gaho)") so cover entries are parsed before stripping.
    match = re.match(
        r'^((?:[A-Za-z][A-Za-z \.]*(?:,\s*)?)+?)\s+["\u201c]([^"\u201d]+)["\u201d]?(?:\s.*)?$',
        title,
    )
    if match:
        member_part = match.group(1).strip().rstrip(",")
        song_title = match.group(2).strip()
        # Try the last name in a comma list, then the full string
        for name in [member_part.split(",")[-1].strip(), member_part]:
            artist_id = resolve_member(name, aliases)
            if artist_id:
                return song_title, artist_id
    # Pattern: name(s) followed by wiki-linked title
    match = re.match(r'^([A-Za-z][A-Za-z ,\.]+?)\s+\[\[(.+?)\]\]', title)
    if match:
        member_name = match.group(1).strip()
        song_title = match.group(2).split("|")[-1].strip()
        artist_id = resolve_member(member_name, aliases)
        if artist_id:
            return song_title, artist_id
    return title, None


def extract_cover_original(title: str) -> str | None:
    """Extract original artist from '(orig. : Artist)' or 'Cover (orig. : Artist)'."""
    match = re.search(r"orig\.?\s*:?\s*([^\)]+)", title, re.IGNORECASE)
    if match:
        return strip_wikilinks(match.group(1)).strip()
    return None


def is_cover(title: str) -> bool:
    return bool(re.search(r"\bcover\b|\borig\b", title, re.IGNORECASE))


# ---------------------------------------------------------------------------
# MediaWiki API fetch
# ---------------------------------------------------------------------------

class FandomScraper(BaseScraper):

    def __init__(self, config: GroupConfig = SKZ_CONFIG):
        super().__init__()
        self.config = config

    def fetch_wikitext(self, page_title: str) -> str:
        url = (
            f"{self.config.fandom_api}?action=query"
            f"&titles={page_title}"
            f"&prop=revisions&rvprop=content&rvslots=main"
            f"&format=json&formatversion=2"
        )
        response = self.get(url)
        data = response.json()
        pages = data["query"]["pages"]
        return pages[0]["revisions"][0]["slots"]["main"]["content"]

    # -----------------------------------------------------------------------
    # SKZ-RECORD
    # -----------------------------------------------------------------------

    def scrape_skz_record(self, db: Session) -> None:
        logger.info("Fetching SKZ-RECORD wikitext...")
        wikitext = self.fetch_wikitext("SKZ-RECORD")

        import os
        os.makedirs("data/raw", exist_ok=True)
        with open("data/raw/fandom_skz_record.txt", "w", encoding="utf-8") as f:
            f.write(wikitext)

        parsed = mwparserfromhell.parse(wikitext)
        inserted = 0

        for table in parsed.filter_tags(matches=lambda n: n.tag == "table" or str(n).startswith("{|")):
            pass  # mwparserfromhell handles tables differently

        # Parse wiki table rows directly from raw wikitext
        # Each row starts with |- and cells are separated by |
        rows = self._parse_wiki_table_rows(wikitext)
        logger.info(f"  SKZ-RECORD: {len(rows)} data rows found")

        for row in rows:
            if len(row) < 4:
                continue

            raw_title = clean(strip_wikilinks(row[2]))
            raw_date = row[3].strip() if len(row) > 3 else ""

            if not raw_title or raw_title.lower() in ("title", "#", ""):
                continue

            # Skip rows that are just numbers (episode number cells)
            if re.match(r"^\d+$", raw_title.strip()):
                continue

            release_date = parse_fandom_date(raw_date)
            song_title, member_artist_id = extract_member_from_title(raw_title, self.config.member_aliases)
            original_artist = extract_cover_original(raw_title)
            cover = is_cover(raw_title)

            # Clean title further — remove "Cover (orig. : X)" suffix
            song_title = re.sub(r'"?\s*Cover.*$', "", song_title, flags=re.IGNORECASE).strip()
            song_title = strip_quotes(song_title)

            if not song_title:
                continue

            # Skip if this release already exists (idempotent re-runs)
            if db.query(Release).filter(
                Release.title == song_title,
                Release.release_subtype == "skz_record",
            ).first():
                logger.debug(f"  Skipping existing SKZ-RECORD: {song_title}")
                continue

            # Create a release for this SKZ-RECORD episode
            release = Release(
                title=song_title,
                release_type="digital_single",
                release_subtype="skz_record",
                release_date=release_date,
                release_date_precision="day" if release_date else "year",
                artist_id=member_artist_id or self.config.artist_id,
                market="GLOBAL",
                fandom_url="https://stray-kids.fandom.com/wiki/SKZ-RECORD",
                is_verified=True,
                source="fandom",
            )
            db.add(release)
            db.flush()

            # Check for existing song or create new one
            existing_song = db.query(Song).filter(Song.title == song_title).first()
            if not existing_song:
                song = Song(
                    title=song_title,
                    language="ko",
                    release_status="released",
                    is_instrumental=False,
                    original_artist=original_artist,
                    fandom_url="https://stray-kids.fandom.com/wiki/SKZ-RECORD",
                    is_verified=True,
                    source="fandom",
                    notes="SKZ-RECORD" + (" (cover)" if cover else ""),
                )
                db.add(song)
                db.flush()

                # Add member credit
                if member_artist_id:
                    db.add(SongCredit(
                        song_id=song.id,
                        artist_id=member_artist_id,
                        role="vocalist",
                    ))
            else:
                song = existing_song

            db.add(Track(release_id=release.id, song_id=song.id))
            inserted += 1
            logger.info(f"  + SKZ-RECORD: {song_title} ({raw_date})")

        db.commit()
        logger.info(f"SKZ-RECORD scrape complete. Inserted: {inserted}")

    # -----------------------------------------------------------------------
    # SKZ-PLAYER
    # -----------------------------------------------------------------------

    def scrape_skz_player(self, db: Session) -> None:
        logger.info("Fetching SKZ-PLAYER wikitext...")
        wikitext = self.fetch_wikitext("SKZ-PLAYER")

        with open("data/raw/fandom_skz_player.txt", "w", encoding="utf-8") as f:
            f.write(wikitext)

        rows = self._parse_wiki_table_rows(wikitext)
        logger.info(f"  SKZ-PLAYER: {len(rows)} data rows found")
        inserted = 0

        for row in rows:
            if len(row) < 4:
                continue

            raw_title = clean(strip_wikilinks(row[2]))
            raw_date = row[3].strip() if len(row) > 3 else ""

            if not raw_title or re.match(r"^\d+$", raw_title.strip()):
                continue
            if raw_title.lower() in ("title", "#", "thumbnail", "date", "runtime", "link"):
                continue

            release_date = parse_fandom_date(raw_date)
            song_title, member_artist_id = extract_member_from_title(raw_title, self.config.member_aliases)
            song_title = strip_quotes(song_title)

            if not song_title:
                continue

            # Skip if this release already exists (idempotent re-runs)
            if db.query(Release).filter(
                Release.title == song_title,
                Release.release_subtype == "skz_player",
            ).first():
                logger.debug(f"  Skipping existing SKZ-PLAYER: {song_title}")
                continue

            release = Release(
                title=song_title,
                release_type="digital_single",
                release_subtype="skz_player",
                release_date=release_date,
                release_date_precision="day" if release_date else "year",
                artist_id=member_artist_id or self.config.artist_id,
                market="GLOBAL",
                fandom_url="https://stray-kids.fandom.com/wiki/SKZ-PLAYER",
                is_verified=True,
                source="fandom",
            )
            db.add(release)
            db.flush()

            existing_song = db.query(Song).filter(Song.title == song_title).first()
            if not existing_song:
                song = Song(
                    title=song_title,
                    language="ko",
                    release_status="released",
                    fandom_url="https://stray-kids.fandom.com/wiki/SKZ-PLAYER",
                    is_verified=True,
                    source="fandom",
                    notes="SKZ-PLAYER",
                )
                db.add(song)
                db.flush()

                if member_artist_id:
                    db.add(SongCredit(
                        song_id=song.id,
                        artist_id=member_artist_id,
                        role="vocalist",
                    ))
            else:
                song = existing_song

            db.add(Track(release_id=release.id, song_id=song.id))
            inserted += 1
            logger.info(f"  + SKZ-PLAYER: {song_title} ({raw_date})")

        db.commit()
        logger.info(f"SKZ-PLAYER scrape complete. Inserted: {inserted}")

    # -----------------------------------------------------------------------
    # Unreleased songs
    # -----------------------------------------------------------------------

    def scrape_unreleased(self, db: Session) -> None:
        logger.info("Fetching Other_unreleased_songs wikitext...")
        wikitext = self.fetch_wikitext("Other_unreleased_songs")

        with open("data/raw/fandom_unreleased.txt", "w", encoding="utf-8") as f:
            f.write(wikitext)

        # Entries are ===Title=== headings followed by paragraph text
        sections = re.findall(
            r"===(.+?)===(.*?)(?====|\Z)",
            wikitext,
            re.DOTALL,
        )
        inserted = 0

        for raw_title, body in sections:
            title = strip_quotes(clean(strip_wikilinks(raw_title)))
            if not title:
                continue

            body_clean = clean(strip_wikilinks(body))

            existing = db.query(Song).filter(Song.title == title).first()
            if existing:
                logger.debug(f"  Skipping existing unreleased: {title}")
                continue

            song = Song(
                title=title,
                language="ko",
                release_status="unreleased",
                is_verified=False,
                source="fandom",
                fandom_url="https://stray-kids.fandom.com/wiki/Other_unreleased_songs",
                notes=body_clean[:500] if body_clean else None,
            )
            db.add(song)
            db.flush()
            inserted += 1
            logger.info(f"  + Unreleased: {title}")

        db.commit()
        logger.info(f"Unreleased scrape complete. Inserted: {inserted}")

    # -----------------------------------------------------------------------
    # Wiki table row parser
    # -----------------------------------------------------------------------

    def _parse_wiki_table_rows(self, wikitext: str) -> list[list[str]]:
        """
        Parse wikitext table rows. Returns list of rows, each row is a list
        of cell strings. Handles both | and || cell separators.
        """
        rows = []
        current_row: list[str] = []
        in_table = False

        for line in wikitext.splitlines():
            stripped = line.strip()

            if stripped.startswith("{|"):
                in_table = True
                continue
            if stripped.startswith("|}"):
                if current_row:
                    rows.append(current_row)
                    current_row = []
                in_table = False
                continue
            if not in_table:
                continue

            if stripped.startswith("|-"):
                if current_row:
                    rows.append(current_row)
                current_row = []
                continue

            # Header row — skip
            if stripped.startswith("!"):
                continue

            # Cell row
            if stripped.startswith("|"):
                cell_content = stripped[1:].strip()
                # Handle || inline multiple cells
                if "||" in cell_content:
                    parts = cell_content.split("||")
                    for part in parts:
                        # Strip cell attributes (e.g. "width=5% |actual content")
                        if "|" in part:
                            part = part.split("|", 1)[-1]
                        current_row.append(part.strip())
                else:
                    # Strip cell attributes
                    if re.match(r"[a-zA-Z].*?\|", cell_content):
                        cell_content = cell_content.split("|", 1)[-1]
                    current_row.append(cell_content.strip())

        return rows
