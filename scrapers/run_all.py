"""
Orchestrates all scrapers in dependency order.
Run locally while the Docker DB container is running:

  poetry run python scrapers/run_all.py
"""
from app.database import SessionLocal
from scrapers.wikipedia_scraper import WikipediaDiscographyScraper
from scrapers.wikipedia_songs_scraper import WikipediaSongsScraper
from scrapers.fandom_scraper import FandomScraper
from scrapers.spotify_scraper import SpotifyScraper


def main():
    db = SessionLocal()
    try:
        print("Phase 1: Wikipedia discography → releases")
        WikipediaDiscographyScraper().scrape_discography(db)

        print("Phase 2: Wikipedia songs list → songs, tracks, credits")
        WikipediaSongsScraper().scrape_songs(db)

        print("Phase 3: Fandom SKZ-RECORD")
        FandomScraper().scrape_skz_record(db)

        print("Phase 3: Fandom SKZ-PLAYER")
        FandomScraper().scrape_skz_player(db)

        print("Phase 3: Fandom unreleased songs")
        FandomScraper().scrape_unreleased(db)

        print("Phase 5: Spotify enrichment")
        SpotifyScraper().enrich_songs(db)

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
