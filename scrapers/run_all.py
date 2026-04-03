"""
Orchestrates all scrapers in dependency order.
Run locally while the Docker DB container is running:

  poetry run python scrapers/run_all.py
"""
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.database import SessionLocal
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track
from scrapers.wikipedia_scraper import WikipediaDiscographyScraper
from scrapers.wikipedia_songs_scraper import WikipediaSongsScraper
from scrapers.wikipedia_song_articles_scraper import WikipediaSongArticlesScraper
from scrapers.fandom_scraper import FandomScraper
from scrapers.spotify_scraper import SpotifyScraper
from scrapers.youtube_scraper import YouTubeScraper


def reconcile_singles(db) -> None:
    """
    Phase 2.5: For every digital_single release with no tracks, find a song
    with a matching title and create the Track link automatically.
    Also normalises stray quote characters in release titles.

    This runs automatically after Phase 2 so a clean rescrape never needs
    manual patching.
    """
    print("Phase 2.5: Reconciling single releases → songs")

    # Fix stray leading/trailing quotes in release titles (e.g. 'Fam" (Korean version)')
    import re
    all_releases = db.query(Release).all()
    for r in all_releases:
        cleaned = re.sub(r'^["\u201c\u201d]+|["\u201d"]+$', "", r.title).strip()
        if cleaned != r.title:
            print(f"  Title fix: {repr(r.title)} → {repr(cleaned)}")
            r.title = cleaned
    db.flush()

    # Link unlinked singles to matching songs
    linked = {t.release_id for t in db.query(Track.release_id).all()}
    singles = (
        db.query(Release)
        .filter(Release.release_type == "digital_single", ~Release.id.in_(linked))
        .all()
    )

    # Regex to extract a version label from a title suffix, e.g. "Fam (Korean version)" → ("Fam", "Korean")
    version_pattern = re.compile(
        r'^(.+?)\s*\(([^)]+?)\s*(?:ver(?:sion)?\.?)?\)\s*$',
        re.IGNORECASE,
    )

    fixed = 0
    unmatched = []
    for release in singles:
        song = (
            db.query(Song).filter(Song.title == release.title).first()
            or db.query(Song).filter(Song.title.ilike(release.title)).first()
        )

        if not song:
            # Try stripping a version suffix to find the parent song
            m = version_pattern.match(release.title)
            if m:
                base_title = m.group(1).strip()
                version_label = m.group(2).strip()
                parent = (
                    db.query(Song).filter(Song.title == base_title).first()
                    or db.query(Song).filter(Song.title.ilike(base_title)).first()
                )
                if parent:
                    # Create a version Song row linked to the parent
                    song = Song(
                        title=release.title,
                        parent_song_id=parent.id,
                        version_label=version_label,
                        language=parent.language,
                        release_status="released",
                        is_verified=True,
                        source="wikipedia",
                    )
                    db.add(song)
                    db.flush()
                    print(f"  Version song created: '{release.title}' → parent '{parent.title}'")

        if song:
            db.add(Track(release_id=release.id, song_id=song.id, is_title_track=True))
            fixed += 1
        else:
            unmatched.append(release.title)

    db.commit()
    print(f"  Linked: {fixed} singles | Unmatched: {len(unmatched)}")
    for t in unmatched:
        print(f"    No song match: {t}")


def deduplicate_songs(db) -> None:
    """
    Phase 4: Automatically merge case-insensitive duplicate songs.

    After Wikipedia (Phase 2) and Fandom (Phase 3) both run, some songs
    end up with two rows that differ only in casing or minor whitespace
    (e.g. "Miroh" from Wikipedia and "miroh" from Fandom).

    Strategy:
      - Group songs by lower(title).
      - Within each group keep the Wikipedia-sourced row (or the first row
        if none is from Wikipedia). The others are duplicates.
      - For each duplicate: re-point its Track and SongCredit rows to the
        keeper, skipping any that would create a unique-constraint conflict.
      - Delete the duplicate song row.
    """
    print("Phase 4: Deduplicating songs...")

    all_songs = db.query(Song).order_by(Song.id).all()

    # Group by normalised title
    groups: dict[str, list[Song]] = {}
    for song in all_songs:
        key = song.title.lower().strip()
        groups.setdefault(key, []).append(song)

    merged = 0
    for key, group in groups.items():
        if len(group) < 2:
            continue

        # Prefer the Wikipedia-sourced row as the keeper
        keeper = next((s for s in group if s.source == "wikipedia"), group[0])
        duplicates = [s for s in group if s.id != keeper.id]

        for dup in duplicates:
            # Migrate Track rows
            dup_tracks = db.query(Track).filter(Track.song_id == dup.id).all()
            for track in dup_tracks:
                conflict = db.query(Track).filter(
                    Track.release_id == track.release_id,
                    Track.song_id == keeper.id,
                ).first()
                if conflict:
                    db.delete(track)
                else:
                    track.song_id = keeper.id

            # Migrate SongCredit rows
            dup_credits = db.query(SongCredit).filter(SongCredit.song_id == dup.id).all()
            for credit in dup_credits:
                conflict = db.query(SongCredit).filter(
                    SongCredit.song_id == keeper.id,
                    SongCredit.artist_id == credit.artist_id,
                    SongCredit.role == credit.role,
                ).first()
                if conflict:
                    db.delete(credit)
                else:
                    credit.song_id = keeper.id

            db.flush()

            # Backfill any fields the keeper is missing from the duplicate
            for field in ("spotify_id", "duration_seconds", "isrc", "fandom_url",
                          "title_korean", "title_japanese", "original_artist"):
                if getattr(keeper, field) is None and getattr(dup, field) is not None:
                    setattr(keeper, field, getattr(dup, field))

            print(f"  Merged '{dup.title}' (id={dup.id}, src={dup.source}) "
                  f"→ keeper id={keeper.id} (src={keeper.source})")
            db.delete(dup)
            merged += 1

    db.commit()
    print(f"Phase 4 complete. Merged {merged} duplicate song(s).")


def main():
    db = SessionLocal()
    try:
        print("Phase 1: Wikipedia discography → releases")
        WikipediaDiscographyScraper().scrape_discography(db)

        print("Phase 2: Wikipedia songs list → songs, tracks, credits")
        WikipediaSongsScraper().scrape_songs(db)

        reconcile_singles(db)

        print("Phase 2.6: Wikipedia song article track listings → versions + missing releases")
        WikipediaSongArticlesScraper().scrape_song_articles(db)

        scraper = FandomScraper()
        print("Phase 3: Fandom SKZ-RECORD")
        scraper.scrape_skz_record(db)

        print("Phase 3: Fandom SKZ-PLAYER")
        scraper.scrape_skz_player(db)

        print("Phase 3: Fandom unreleased songs")
        scraper.scrape_unreleased(db)

        deduplicate_songs(db)

        print("Phase 5: Spotify enrichment")
        SpotifyScraper().enrich_songs(db)

        print("Phase 6: YouTube MV enrichment")
        YouTubeScraper().enrich_songs(db)

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
