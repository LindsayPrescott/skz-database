"""
Orchestrates all scrapers in dependency order.
Run locally while the Docker DB container is running:

  poetry run python -m scrapers.run_all

Run specific phases:

  poetry run python -m scrapers.run_all --phases youtube
  poetry run python -m scrapers.run_all --phases fandom dedup-releases dedup-songs

Available phases (run in order when specified):
  wikipedia           Phase 1  — Wikipedia discography → releases
  wikipedia-songs     Phase 2  — Wikipedia songs list → songs, tracks, credits
  reconcile           Phase 2.5 — Link single releases to songs
  wikipedia-articles  Phase 2.6 — Wikipedia song articles → versions + missing releases
  fandom              Phase 3  — Fandom SKZ-RECORD, SKZ-PLAYER, unreleased songs
  dedup-releases      Phase 3.5 — Deduplicate release rows
  dedup-songs         Phase 4  — Deduplicate song rows
  spotify             Phase 5  — Spotify enrichment
  youtube             Phase 6  — YouTube MV enrichment
"""
import argparse
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.database import SessionLocal
from scrapers.config import SKZ_CONFIG
from app.models.charts import ChartEntry, ReleaseSales
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track
from scrapers.wikipedia_scraper import WikipediaDiscographyScraper
from scrapers.wikipedia_songs_scraper import WikipediaSongsScraper
from scrapers.wikipedia_song_articles_scraper import WikipediaSongArticlesScraper
from scrapers.fandom_scraper import FandomScraper
from scrapers.spotify_scraper import SpotifyScraper
from scrapers.youtube_scraper import YouTubeScraper
from scrapers.utils import find_song, find_song_by_any_title, link_song_to_release


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
        song = find_song(db, release.title)

        if not song:
            # Try stripping a version suffix to find the parent song
            m = version_pattern.match(release.title)
            if m:
                base_title = m.group(1).strip()
                version_label = m.group(2).strip()
                parent = find_song(db, base_title)
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

        if not song:
            # Handle compound slash-separated Japanese/Korean/English version singles,
            # e.g. "Social Path / Super Bowl -Japanese ver.-"
            #      "Scars / ソリクン -Japanese ver.-"
            # Strip the language-version suffix, split on "/", look up each part.
            stripped = re.sub(
                r"\s+-(?:Japanese|Korean|English)\s+ver\.-\s*$",
                "", release.title, flags=re.IGNORECASE,
            ).strip()
            if stripped != release.title and "/" in stripped:
                parts = [p.strip() for p in stripped.split("/")]
                linked_any = False
                for part in parts:
                    s = find_song_by_any_title(db, part)
                    if s:
                        link_song_to_release(db, s, release.id, is_title_track=True)
                        linked_any = True
                        print(f"  Compound link: '{release.title}' → '{s.title}'")
                if linked_any:
                    fixed += 1
                    continue

        if song:
            link_song_to_release(db, song, release.id, is_title_track=True)
            fixed += 1
        else:
            unmatched.append(release.title)

    db.commit()
    print(f"  Linked: {fixed} singles | Unmatched: {len(unmatched)}")
    for t in unmatched:
        print(f"    No song match: {t}")


def deduplicate_releases(db) -> None:
    """
    Phase 3.5: Automatically merge duplicate release rows.

    Before the Fandom scraper dedup check was added, every pipeline run created
    new skz_record / skz_player releases with the same title.  This collapses
    those into a single row.

    Strategy:
      - Group releases by normalised (title, release_type).
      - Within each group keep the release with the most complete data:
          1. Prefer releases that have a release_date.
          2. Then prefer by source: wikipedia > spotify > fandom > manual.
          3. Then keep the lowest id (earliest created).
      - Re-point Track, ChartEntry, and ReleaseSales rows to the keeper,
        skipping any Track that would create a unique-constraint conflict.
      - Backfill fields the keeper is missing from the duplicate.
      - Delete the duplicate.
    """
    print("Phase 3.5: Deduplicating releases...")

    SOURCE_PRIORITY = {"wikipedia": 0, "spotify": 1, "fandom": 2, "manual": 3}

    all_releases = db.query(Release).order_by(Release.id).all()

    groups: dict[tuple, list] = {}
    for r in all_releases:
        key = (r.title.lower().strip(), r.release_type)
        groups.setdefault(key, []).append(r)

    merged = 0
    for key, group in groups.items():
        if len(group) < 2:
            continue

        def sort_key(r):
            has_date = 0 if r.release_date else 1
            priority = SOURCE_PRIORITY.get(r.source or "manual", 3)
            return (has_date, priority, r.id)

        keeper = sorted(group, key=sort_key)[0]
        duplicates = [r for r in group if r.id != keeper.id]

        for dup in duplicates:
            # Migrate Track rows
            for track in db.query(Track).filter(Track.release_id == dup.id).all():
                conflict = db.query(Track).filter(
                    Track.release_id == keeper.id,
                    Track.song_id == track.song_id,
                ).first()
                if conflict:
                    db.delete(track)
                else:
                    track.release_id = keeper.id

            # Migrate ChartEntry rows
            for entry in db.query(ChartEntry).filter(ChartEntry.release_id == dup.id).all():
                entry.release_id = keeper.id

            # Migrate ReleaseSales rows
            for sale in db.query(ReleaseSales).filter(ReleaseSales.release_id == dup.id).all():
                sale.release_id = keeper.id

            db.flush()

            # Backfill any fields the keeper is missing from the duplicate
            for field in ("release_date", "release_date_precision", "label", "formats",
                          "wikipedia_url", "fandom_url", "cover_image_url", "catalog_number"):
                if getattr(keeper, field) is None and getattr(dup, field) is not None:
                    setattr(keeper, field, getattr(dup, field))

            print(f"  Merged '{dup.title}' ({dup.release_type}, id={dup.id}, src={dup.source}) "
                  f"→ keeper id={keeper.id} (src={keeper.source})")
            db.delete(dup)
            merged += 1

    db.commit()
    print(f"Phase 3.5 complete. Merged {merged} duplicate release(s).")


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


PHASES = [
    "wikipedia",
    "wikipedia-songs",
    "reconcile",
    "wikipedia-articles",
    "fandom",
    "dedup-releases",
    "dedup-songs",
    "spotify",
    "youtube",
]


def run_phases(phases: list[str]) -> None:
    db = SessionLocal()
    try:
        if "wikipedia" in phases:
            print("Phase 1: Wikipedia discography → releases")
            WikipediaDiscographyScraper(SKZ_CONFIG).scrape_discography(db)

        if "wikipedia-songs" in phases:
            print("Phase 2: Wikipedia songs list → songs, tracks, credits")
            WikipediaSongsScraper(SKZ_CONFIG).scrape_songs(db)

        if "reconcile" in phases:
            reconcile_singles(db)

        if "wikipedia-articles" in phases:
            print("Phase 2.6: Wikipedia song article track listings → versions + missing releases")
            WikipediaSongArticlesScraper().scrape_song_articles(db)

        if "fandom" in phases:
            scraper = FandomScraper(SKZ_CONFIG)
            print("Phase 3: Fandom SKZ-RECORD")
            scraper.scrape_skz_record(db)
            print("Phase 3: Fandom SKZ-PLAYER")
            scraper.scrape_skz_player(db)
            print("Phase 3: Fandom unreleased songs")
            scraper.scrape_unreleased(db)

        if "dedup-releases" in phases:
            deduplicate_releases(db)

        if "dedup-songs" in phases:
            deduplicate_songs(db)

        if "spotify" in phases:
            print("Phase 5: Spotify enrichment")
            SpotifyScraper(SKZ_CONFIG).enrich_songs(db)

        if "youtube" in phases:
            print("Phase 6: YouTube MV enrichment")
            YouTubeScraper(SKZ_CONFIG).enrich_songs(db)

        print("Done.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SKZ database scrapers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--phases",
        nargs="+",
        choices=PHASES,
        metavar="PHASE",
        help=(
            "One or more phases to run. If omitted, all phases run in order. "
            f"Available: {', '.join(PHASES)}"
        ),
    )
    args = parser.parse_args()
    run_phases(args.phases if args.phases else PHASES)


if __name__ == "__main__":
    main()
