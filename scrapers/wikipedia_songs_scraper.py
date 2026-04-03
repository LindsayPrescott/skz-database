"""
Phase 2 scraper: Wikipedia songs list → songs, tracks, song_credits

URL: https://en.wikipedia.org/wiki/List_of_songs_recorded_by_Stray_Kids

Table columns: Song | Artist(s) | Lyrics | Composition | Arrangement/producer(s) | Album | Year

Symbol key (in song title cell):
  †  = has Korean + Japanese versions
  ‡  = has Korean + Japanese + English versions
  ⁂  = has Korean + English versions
  #  = has English + Japanese versions
"""
import re
import logging
from difflib import get_close_matches

from bs4 import BeautifulSoup, Tag
from sqlalchemy.orm import Session

from app.models.artists import Artist
from app.models.releases import Release
from app.models.songs import Song, Track
from app.models.credits import SongCredit
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SONGS_URL = "https://en.wikipedia.org/wiki/List_of_songs_recorded_by_Stray_Kids"

# Column indices (0-based)
COL_SONG        = 0
COL_ARTIST      = 1
COL_LYRICS      = 2
COL_COMPOSITION = 3
COL_ARRANGEMENT = 4
COL_ALBUM       = 5
COL_YEAR        = 6

# Credit role per column
CREDIT_ROLE_MAP = {
    COL_LYRICS:      "lyricist",
    COL_COMPOSITION: "composer",
    COL_ARRANGEMENT: "arranger",
}

# Symbol → language version flags
SYMBOL_FLAGS = {
    "†":  {"has_japanese_ver": True},
    "‡":  {"has_japanese_ver": True, "has_english_ver": True},
    "⁂":  {"has_english_ver": True},
    "#":  {"has_english_ver": True, "has_japanese_ver": True},
}


# ---------------------------------------------------------------------------
# Text helpers (duplicated from wikipedia_scraper to keep files independent)
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation — used for fuzzy release matching."""
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


# ---------------------------------------------------------------------------
# Artist name → DB id cache
# ---------------------------------------------------------------------------

class ArtistCache:
    """
    Loads all artists from DB once, then resolves name strings to IDs.
    Handles common aliases and romanization variants.
    """

    ALIASES = {
        "straykids": 1, "stray kids": 1,
        "3racha": 2, "three racha": 2,
        "danceracha": 3, "dance racha": 3,
        "vocalracha": 4, "vocal racha": 4,
        "bang chan": 5, "chris": 5, "cb97": 5,
        "lee know": 6, "leeknow": 6, "minho": 6,
        "changbin": 7, "seo changbin": 7, "spearb": 7,
        "hyunjin": 8, "hwang hyunjin": 8,
        "han": 9, "han jisung": 9, "j.one": 9,
        "felix": 10, "lee felix": 10,
        "seungmin": 11, "kim seungmin": 11,
        "i.n": 12, "in": 12, "yang jeongin": 12,
        "woojin": 13, "kim woojin": 13,
    }

    def resolve(self, name: str) -> int | None:
        key = clean(name).lower()
        return self.ALIASES.get(key)


# ---------------------------------------------------------------------------
# Release title → DB id cache (for linking songs to releases via tracks)
# ---------------------------------------------------------------------------

class ReleaseCache:

    def __init__(self, db: Session):
        rows = db.query(Release.id, Release.title).all()
        self._norm_map: dict[str, int] = {}
        self._titles: list[str] = []
        for rid, title in rows:
            norm = normalize_title(title)
            self._norm_map[norm] = rid
            self._titles.append(norm)

    def find(self, raw_title: str) -> int | None:
        norm = normalize_title(raw_title)
        if norm in self._norm_map:
            return self._norm_map[norm]
        # Fuzzy fallback — handles minor punctuation differences
        matches = get_close_matches(norm, self._titles, n=1, cutoff=0.82)
        if matches:
            return self._norm_map[matches[0]]
        return None


# ---------------------------------------------------------------------------
# Cell parsers
# ---------------------------------------------------------------------------

def parse_song_cell(cell: Tag) -> dict:
    """
    Extract title (English), title_korean, title_japanese, and language flags
    from the Song column cell.

    Cell formats seen:
      "Title"†
      "Title" (한국어; 日本語)†
      "Title" (한국어; 日本語)
    """
    result = {
        "title": "",
        "title_korean": None,
        "title_japanese": None,
        "has_korean_ver": True,   # All songs are primarily Korean unless indicated
        "has_english_ver": False,
        "has_japanese_ver": False,
        "fandom_url": None,
    }

    # Capture the link href if present
    link = cell.find("a")
    if link and link.get("href", "").startswith("/wiki/"):
        result["fandom_url"] = "https://en.wikipedia.org" + link["href"]

    raw = clean(cell.get_text())

    # Extract language symbols before stripping them
    for symbol, flags in SYMBOL_FLAGS.items():
        if symbol in raw:
            result.update(flags)
            raw = raw.replace(symbol, "")

    # Extract parenthetical Korean/Japanese: (한국어; 日本語) or (한국어)
    paren_match = re.search(r"\(([^)]+)\)", raw)
    if paren_match:
        paren = paren_match.group(1)
        parts = [p.strip() for p in paren.split(";")]
        if parts:
            result["title_korean"] = parts[0] if parts[0] else None
        if len(parts) > 1:
            result["title_japanese"] = parts[1] if parts[1] else None
        raw = raw[:paren_match.start()].strip()

    # Strip surrounding quotes (straight and curly)
    title = raw.strip('"').strip("\u201c\u201d").strip()
    # Clean inner quotes around " / " separators: "Title1" / "Title2" → Title1 / Title2
    title = re.sub(r'["\u201c\u201d]+\s*/\s*["\u201c\u201d]+', ' / ', title)
    result["title"] = title

    return result


def parse_artist_cell(cell: Tag) -> str:
    """Return cleaned artist string from the Artist(s) column."""
    return clean(cell.get_text())


def parse_credit_names(cell: Tag) -> list[str]:
    """
    Split a Lyrics/Composition/Arrangement cell into individual name strings.
    Names are separated by <br> tags.
    """
    for br in cell.find_all("br"):
        br.replace_with("\n")
    raw = clean(cell.get_text())
    names = []
    for part in raw.split("\n"):
        part = clean(part)
        # Strip parenthetical unit notes like "(3RACHA)" from credit names
        part = re.sub(r"\(.*?\)", "", part).strip()
        if part:
            names.append(part)
    return names


def parse_album_cell(cell: Tag) -> str | None:
    """
    Return the first album title from the cell, or None for non-album singles.
    Albums may be separated by <br> tags or " and " text.
    Split BEFORE calling clean() so newlines aren't collapsed into spaces.
    """
    for br in cell.find_all("br"):
        br.replace_with("\n")
    # Strip footnotes but preserve newlines — don't call clean() yet
    raw = re.sub(r"\[.*?\]", "", cell.get_text())
    parts = [p.strip() for p in raw.split("\n") if p.strip()]
    if not parts:
        return None
    first = parts[0]
    if first.lower() in ("non-album single", "—", ""):
        return None
    # Also handle " and " within a single line
    first = re.split(r"\s+and\s+", first, maxsplit=1)[0]
    return first.strip()


# ---------------------------------------------------------------------------
# Main scraper class
# ---------------------------------------------------------------------------

class WikipediaSongsScraper(BaseScraper):

    def scrape_songs(self, db: Session) -> None:
        logger.info("Fetching Wikipedia songs list page...")
        soup = self.get_soup(SONGS_URL)

        # Save raw HTML
        import os
        os.makedirs("data/raw", exist_ok=True)
        with open("data/raw/wikipedia_songs.html", "w", encoding="utf-8") as f:
            f.write(str(soup))

        artist_cache = ArtistCache()
        release_cache = ReleaseCache(db)

        # First wikitable is the symbol key legend — skip it, use the second
        tables = soup.find_all("table", class_="wikitable")
        table = next((t for t in tables if len(t.find_all("tr")) > 10), None)
        if not table:
            raise RuntimeError("Could not find songs wikitable on page")

        rows = table.find_all("tr")
        inserted = 0
        skipped = 0

        for row in rows:
            # Skip header rows
            if row.find("th") and not row.find("td"):
                continue

            cells = row.find_all(["td", "th"])
            if len(cells) < 7:
                continue

            # --- Parse song cell ---
            song_data = parse_song_cell(cells[COL_SONG])
            if not song_data["title"]:
                continue

            # --- Deduplicate ---
            existing = db.query(Song).filter(Song.title == song_data["title"]).first()
            if existing:
                skipped += 1
                logger.debug(f"  Skipping existing: {song_data['title']}")
                # Backfill wikipedia_url if it was missing (e.g. first scrape ran before this field existed)
                if existing.wikipedia_url is None and song_data.get("fandom_url"):
                    existing.wikipedia_url = song_data["fandom_url"]
                continue

            # --- Year ---
            year_text = clean(cells[COL_YEAR].get_text())
            year = int(year_text) if year_text.isdigit() else None

            # --- Create Song row ---
            song = Song(
                title=song_data["title"],
                title_korean=song_data["title_korean"],
                title_japanese=song_data["title_japanese"],
                has_korean_ver=song_data["has_korean_ver"],
                has_english_ver=song_data["has_english_ver"],
                has_japanese_ver=song_data["has_japanese_ver"],
                language="ko",
                release_status="released",
                wikipedia_url=song_data.get("fandom_url"),
                is_verified=True,
                source="wikipedia",
                notes=f"Year: {year}" if year else None,
            )
            db.add(song)
            db.flush()

            # --- Track: link song to release ---
            album_title = parse_album_cell(cells[COL_ALBUM])
            if album_title:
                release_id = release_cache.find(album_title)
                if release_id:
                    track = Track(
                        release_id=release_id,
                        song_id=song.id,
                        is_title_track=False,
                    )
                    db.add(track)
                else:
                    logger.warning(f"  No release match for album: '{album_title}' (song: {song.title})")

            # --- Credits ---
            self._insert_credits(song, cells, artist_cache, db)

            inserted += 1
            logger.info(f"  + {song.title}")

        db.commit()
        logger.info(f"Songs scrape complete. Inserted: {inserted}, Skipped (duplicates): {skipped}")

    def _insert_credits(
        self,
        song: Song,
        cells: list[Tag],
        artist_cache: ArtistCache,
        db: Session,
    ) -> None:
        for col_idx, role in CREDIT_ROLE_MAP.items():
            if col_idx >= len(cells):
                continue
            names = parse_credit_names(cells[col_idx])
            for name in names:
                if not name:
                    continue
                artist_id = artist_cache.resolve(name)
                credit = SongCredit(
                    song_id=song.id,
                    artist_id=artist_id,
                    credit_name_raw=None if artist_id else name,
                    role=role,
                    is_primary=True,
                )
                db.add(credit)
