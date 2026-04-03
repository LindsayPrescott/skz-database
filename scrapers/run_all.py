"""
Orchestrates all scrapers in dependency order.
Run locally while the Docker DB container is running:

  poetry run python scrapers/run_all.py
"""
from app.database import SessionLocal
from app.models.releases import Release
from app.models.songs import Song, Track
from scrapers.wikipedia_scraper import WikipediaDiscographyScraper
from scrapers.wikipedia_songs_scraper import WikipediaSongsScraper
from scrapers.fandom_scraper import FandomScraper
from scrapers.spotify_scraper import SpotifyScraper


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

    fixed = 0
    unmatched = []
    for release in singles:
        song = (
            db.query(Song).filter(Song.title == release.title).first()
            or db.query(Song).filter(Song.title.ilike(release.title)).first()
        )
        if song:
            db.add(Track(release_id=release.id, song_id=song.id, is_title_track=True))
            fixed += 1
        else:
            unmatched.append(release.title)

    db.commit()
    print(f"  Linked: {fixed} singles | Unmatched: {len(unmatched)}")
    for t in unmatched:
        print(f"    No song match: {t}")


def main():
    db = SessionLocal()
    try:
        print("Phase 1: Wikipedia discography → releases")
        WikipediaDiscographyScraper().scrape_discography(db)

        print("Phase 2: Wikipedia songs list → songs, tracks, credits")
        WikipediaSongsScraper().scrape_songs(db)

        reconcile_singles(db)

        scraper = FandomScraper()
        print("Phase 3: Fandom SKZ-RECORD")
        scraper.scrape_skz_record(db)

        print("Phase 3: Fandom SKZ-PLAYER")
        scraper.scrape_skz_player(db)

        print("Phase 3: Fandom unreleased songs")
        scraper.scrape_unreleased(db)

        print("Phase 5: Spotify enrichment")
        SpotifyScraper().enrich_songs(db)

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
