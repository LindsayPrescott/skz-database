"""
Phase 3 scraper: Stray Kids Fandom Wiki via MediaWiki API.

Targets:
  - SKZ-RECORD releases and tracks
  - SKZ-PLAYER releases and tracks
  - Unreleased / snippet songs
  - Solo songs
  - Unit songs

MediaWiki API base: https://stray-kids.fandom.com/api.php
"""
import json

import mwparserfromhell
from sqlalchemy.orm import Session

from scrapers.base_scraper import BaseScraper

FANDOM_API = "https://stray-kids.fandom.com/api.php"

PAGES_TO_SCRAPE = [
    "SKZ-RECORD",
    "SKZ-PLAYER",
    "Other_unreleased_songs",
]


class FandomScraper(BaseScraper):

    def fetch_wikitext(self, page_title: str) -> str:
        """Fetch raw wikitext for a page via the MediaWiki API."""
        params = {
            "action": "query",
            "titles": page_title,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        }
        response = self.get(FANDOM_API + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
        data = response.json()
        pages = data["query"]["pages"]
        return pages[0]["revisions"][0]["slots"]["main"]["content"]

    def parse_wikitext(self, wikitext: str) -> mwparserfromhell.wikicode.Wikicode:
        return mwparserfromhell.parse(wikitext)

    def scrape_skz_record(self, db: Session) -> None:
        """Scrape SKZ-RECORD page and insert Release/Song/Track rows."""
        # TODO: implement in Phase 3
        raise NotImplementedError

    def scrape_skz_player(self, db: Session) -> None:
        """Scrape SKZ-PLAYER page and insert Release/Song/Track rows."""
        # TODO: implement in Phase 3
        raise NotImplementedError

    def scrape_unreleased(self, db: Session) -> None:
        """Scrape unreleased/snippet song entries."""
        # TODO: implement in Phase 3
        raise NotImplementedError
