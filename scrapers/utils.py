"""
Shared utilities for the SKZ database scrapers.

Centralises text cleaning, quote stripping, title normalisation,
member alias resolution, and common DB lookup / link helpers that
were previously duplicated across individual scraper files.
"""
import re
from sqlalchemy.orm import Session

from app.models.songs import Song, Track
from app.models.releases import Release


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    """
    Strip footnote markers [1], HTML ref tags, other HTML tags,
    and collapse extra whitespace.  The superset of all three
    previous local clean() functions.
    """
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_quotes(text: str) -> str:
    """Remove surrounding straight and curly quote characters."""
    text = text.strip()
    text = re.sub(r'^["\u201c\u201d\u2018\u2019]+|["\u201d\u2019"]+$', "", text)
    return text.strip()


def normalize_release_title(title: str) -> str:
    """Lowercase + strip punctuation for fuzzy release matching."""
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def normalize_title(title: str) -> str:
    """
    Normalize a title from any external source for DB matching:
      - Curly/modifier apostrophes (U+2019, U+02BC) → straight apostrophe (U+0027)
      - " : " → ": " (space-colon-space variant, e.g. Spotify's "Mixtape : OH")
      - Leading "#" stripped (e.g. "#LoveSTAY" → "LoveSTAY")
    Idempotent — safe to call on already-normalised titles.
    """
    title = title.replace("\u2019", "'").replace("\u02bc", "'")
    title = re.sub(r"\s+:\s+", ": ", title)
    title = title.lstrip("#")
    return title


# ---------------------------------------------------------------------------
# Artist / member resolution
# ---------------------------------------------------------------------------

# Canonical map of member name variants → artist_id.
# Merges the previously diverged dicts in fandom_scraper and wikipedia_songs_scraper.
MEMBER_ALIASES: dict[str, int] = {
    "straykids": 1, "stray kids": 1,
    "3racha": 2, "three racha": 2,
    "danceracha": 3, "dance racha": 3,
    "vocalracha": 4, "vocal racha": 4,
    "bang chan": 5, "bangchan": 5, "chan": 5, "chris": 5, "cb97": 5,
    "lee know": 6, "leeknow": 6, "minho": 6,
    "changbin": 7, "seo changbin": 7, "spearb": 7,
    "hyunjin": 8, "hwang hyunjin": 8,
    "han": 9, "han jisung": 9, "jisung": 9, "j.one": 9,
    "felix": 10, "lee felix": 10,
    "seungmin": 11, "kim seungmin": 11,
    "i.n": 12, "in": 12, "yang jeongin": 12, "jeongin": 12,
    "woojin": 13, "kim woojin": 13,
}

# Lowercase member names used for member-suffix detection in Spotify titles.
MEMBER_NAMES: frozenset[str] = frozenset({
    "bang chan", "lee know", "changbin", "hyunjin", "han", "felix",
    "seungmin", "i.n", "minho", "jisung", "chris",
})


def resolve_member(name: str) -> int | None:
    """Return artist_id for a member name, or None if not recognised."""
    return MEMBER_ALIASES.get(name.lower().strip())


# ---------------------------------------------------------------------------
# DB lookup helpers
# ---------------------------------------------------------------------------

def find_song_by_any_title(db: Session, title: str) -> "Song | None":
    """
    Find a song by any title field (title, title_japanese, title_korean),
    with normalization applied to each.  Used when looking up individual
    parts of a compound release title like "Scars / ソリクン -Japanese ver.-".
    """
    return (
        find_song(db, title)
        or db.query(Song).filter(Song.title_japanese == title).first()
        or db.query(Song).filter(Song.title_korean == title).first()
    )


def find_song(db: Session, title: str) -> "Song | None":
    """
    Find a song by title with progressive fallbacks:
      1. Exact match
      2. Case-insensitive match
      3. Normalised title (apostrophes, colon spacing, # prefix) — exact then ilike
    """
    song = (
        db.query(Song).filter(Song.title == title).first()
        or db.query(Song).filter(Song.title.ilike(title)).first()
    )
    if song:
        return song
    norm = normalize_title(title)
    if norm != title:
        return (
            db.query(Song).filter(Song.title == norm).first()
            or db.query(Song).filter(Song.title.ilike(norm)).first()
        )
    return None


def find_release(db: Session, title: str) -> "Release | None":
    """
    Find a release by title with progressive fallbacks:
      1. Exact match
      2. Case-insensitive match
      3. Normalised title — exact then ilike
    """
    release = (
        db.query(Release).filter(Release.title == title).first()
        or db.query(Release).filter(Release.title.ilike(title)).first()
    )
    if release:
        return release
    norm = normalize_title(title)
    if norm != title:
        return (
            db.query(Release).filter(Release.title == norm).first()
            or db.query(Release).filter(Release.title.ilike(norm)).first()
        )
    return None


def link_song_to_release(
    db: Session,
    song: "Song",
    release_id: int,
    track_number: int | None = None,
    disc_number: int | None = None,
    is_title_track: bool = False,
) -> "Track":
    """
    Create a Track row linking song to release if one doesn't already exist.
    Returns the existing or newly-created Track.
    """
    existing = db.query(Track).filter(
        Track.release_id == release_id,
        Track.song_id == song.id,
    ).first()
    if existing:
        return existing
    track = Track(
        release_id=release_id,
        song_id=song.id,
        track_number=track_number,
        disc_number=disc_number,
        is_title_track=is_title_track,
    )
    db.add(track)
    return track
