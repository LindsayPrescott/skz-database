"""
Phase 1 scraper: Wikipedia discography page → releases + chart_entries + release_sales

URL: https://en.wikipedia.org/wiki/Stray_Kids_discography

Strategy:
  - Walk the page finding every <h2>/<h3> heading followed by a wikitable
  - Map heading text to a release_type value
  - For album/EP/mixtape tables: parse Title + Details column (date, label, formats)
  - For singles tables: parse Title + Year column
  - Extract chart positions → chart_entries rows
  - Extract sales and certifications
"""
import re
import time
import logging
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag
from sqlalchemy.orm import Session

from app.models.releases import Release
from app.models.charts import ChartEntry, ReleaseSales
from scrapers.base_scraper import BaseScraper
from scrapers.config import GroupConfig, SKZ_CONFIG
from scrapers.utils import clean, strip_quotes

logger = logging.getLogger(__name__)

# Tables we want to skip entirely
SKIP_HEADINGS = {"videography", "video albums", "music videos", "other videos"}

# Which tables have a "Details" column (vs a plain "Year" column)
DETAIL_COLUMN_TYPES = {"studio_album", "compilation_album", "repackage", "ep", "mixtape", "single_album"}

# Chart name mapping: column header text → (chart_name, chart_region)
CHART_COLUMN_MAP = {
    "kor":          ("Gaon Album", "KR"),
    "aus":          ("ARIA", "AU"),
    "can":          ("Billboard Canadian Albums", "CA"),
    "fra":          ("SNEP", "FR"),
    "ger":          ("Offizielle Deutsche Charts", "DE"),
    "jpn":          ("Oricon Albums", "JP"),
    "jpn cmb.":     ("Billboard Japan Hot Albums", "JP"),
    "jpn hot":      ("Billboard Japan Hot 100", "JP"),
    "nz":           ("RMNZ", "NZ"),
    "nz hot":       ("RMNZ Hot Singles", "NZ"),
    "uk":           ("UK Albums Chart", "UK"),
    "uk sales":     ("UK Singles Sales", "UK"),
    "us":           ("Billboard 200", "US"),
    "us world":     ("Billboard World Albums", "US"),
    "ww":           ("Billboard Global 200", "GLOBAL"),
    "us dance dig.":("Billboard Dance/Electronic Digital Songs", "US"),
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def parse_release_date(text: str) -> tuple[date | None, str]:
    """
    Parse a date string into (date, precision).
    Returns (None, 'day') if unparseable.
    """
    text = clean(text)
    for fmt, precision in [
        ("%B %d, %Y", "day"),
        ("%d %B %Y", "day"),
        ("%Y-%m-%d", "day"),
        ("%B %Y", "month"),
        ("%Y", "year"),
    ]:
        try:
            return datetime.strptime(text, fmt).date(), precision
        except ValueError:
            continue
    return None, "day"


def parse_chart_position(text: str) -> int | None:
    """Return integer chart position, or None for '—' / empty cells."""
    text = clean(text)
    if text in ("—", "", "—", "-"):
        return None
    try:
        return int(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Page parsing helpers
# ---------------------------------------------------------------------------

def get_heading_text(tag: Tag) -> str:
    """Extract clean lowercase text from an h2/h3 tag."""
    # Wikipedia headings wrap text in a <span class="mw-headline">
    span = tag.find("span", class_="mw-headline")
    if span:
        return clean(span.get_text()).lower()
    return clean(tag.get_text()).lower()


def parse_details_cell(cell: Tag) -> dict:
    """
    Parse the 'Details' <td> cell found in album/EP tables.
    Returns dict with keys: release_date, release_date_precision, label, formats
    """
    result = {"release_date": None, "release_date_precision": "day", "label": None, "formats": None}
    items = cell.find_all("li")
    for li in items:
        text = clean(li.get_text())
        lower = text.lower()
        if lower.startswith("released:"):
            date_str = text[len("released:"):].strip()
            result["release_date"], result["release_date_precision"] = parse_release_date(date_str)
        elif lower.startswith("label:"):
            result["label"] = text[len("label:"):].strip()
        elif lower.startswith("format") or lower.startswith("format:"):
            result["formats"] = text.split(":", 1)[-1].strip()
    return result


def parse_title_cell(cell: Tag) -> str:
    """Extract the release/song title from a <th scope='row'> cell."""
    # Strip featured artist notation like "(with Alesso and CORSAK)"
    # by grabbing only the first text node / link text before any <br>
    for br in cell.find_all("br"):
        br.replace_with(" ")
    # Remove small text spans (featured artist, version notes)
    for small in cell.find_all("span", style=lambda s: s and "font-size" in s):
        small.decompose()
    title = clean(cell.get_text())
    title = strip_quotes(title)
    # Remove closing quote embedded before a parenthetical, e.g. 'Fam" (Korean version)'
    title = re.sub(r'["\u201d"]+\s*(?=\()', ' ', title).strip()
    return title


def parse_chart_headers(header_row: Tag) -> list[tuple[int, str, str]]:
    """
    Given the header <tr>, return a list of (column_index, chart_name, chart_region)
    for every chart column we recognise. Accounts for colspan on chart group headers.
    """
    charts = []
    col_idx = 0
    for th in header_row.find_all("th"):
        text = clean(th.get_text()).lower()
        colspan = int(th.get("colspan", 1))
        if text in CHART_COLUMN_MAP:
            chart_name, region = CHART_COLUMN_MAP[text]
            charts.append((col_idx, chart_name, region))
        col_idx += colspan
    return charts


def get_all_td_values(row: Tag) -> list[str]:
    """
    Flatten all <td> cells in a row into a list of clean strings,
    expanding rowspan/colspan is not needed for our use case since
    we only care about chart position numbers.
    """
    return [clean(td.get_text()) for td in row.find_all("td")]


# ---------------------------------------------------------------------------
# Main scraper class
# ---------------------------------------------------------------------------

class WikipediaDiscographyScraper(BaseScraper):

    def __init__(self, config: GroupConfig = SKZ_CONFIG):
        super().__init__()
        self.config = config

    def scrape_discography(self, db: Session) -> None:
        logger.info("Fetching Wikipedia discography page...")
        soup = self.get_soup(self.config.wikipedia_discography_url)

        # Save raw HTML for debugging
        import os
        os.makedirs("data/raw", exist_ok=True)
        with open("data/raw/wikipedia_discography.html", "w", encoding="utf-8") as f:
            f.write(str(soup))

        current_release_type = None

        # Walk every element in the page body looking for headings then tables
        content = soup.find("div", id="mw-content-text")
        if not content:
            raise RuntimeError("Could not find page content div")

        for element in content.descendants:
            if not isinstance(element, Tag):
                continue

            # Track the current section heading
            if element.name in ("h2", "h3"):
                heading = get_heading_text(element)
                if heading in SKIP_HEADINGS:
                    current_release_type = None
                elif heading in self.config.heading_to_release_type:
                    current_release_type = self.config.heading_to_release_type[heading]
                    logger.info(f"  Section: {heading} → {current_release_type}")
                continue

            # Process wikitables under a known heading
            if (
                element.name == "table"
                and "wikitable" in element.get("class", [])
                and current_release_type is not None
            ):
                self._scrape_table(element, current_release_type, db)
                # Reset so we don't re-process the same table via inner elements
                current_release_type = None

        db.commit()
        logger.info("Discography scrape complete.")

    def _scrape_table(self, table: Tag, release_type: str, db: Session) -> None:
        rows = table.find_all("tr")
        if len(rows) < 2:
            return

        # Build chart column map from header row(s)
        # Wikipedia sometimes has two header rows (group + individual chart names)
        chart_columns: list[tuple[int, str, str]] = []
        data_rows = []
        for row in rows:
            ths = row.find_all("th")
            tds = row.find_all("td")
            if ths and not tds:
                # This is a header row — try to extract chart columns
                cols = parse_chart_headers(row)
                if cols:
                    chart_columns = cols
            else:
                data_rows.append(row)

        use_details_column = release_type in DETAIL_COLUMN_TYPES

        for row in data_rows:
            title_cell = row.find("th", {"scope": "row"})
            if not title_cell:
                continue

            title = parse_title_cell(title_cell)
            if not title:
                continue

            # Skip rows that are clearly section dividers
            if title.lower() in ("title", ""):
                continue

            # Parse date/label/formats
            tds = row.find_all("td")
            release_date = None
            release_date_precision = "day"
            label = None
            formats = None

            if use_details_column and tds:
                details = parse_details_cell(tds[0])
                release_date = details["release_date"]
                release_date_precision = details["release_date_precision"]
                label = details["label"]
                formats = details["formats"]
                chart_tds = tds[1:]  # Chart columns start after Details
            elif tds:
                # Singles tables: first <td> is Year
                year_text = clean(tds[0].get_text())
                if year_text.isdigit():
                    release_date, release_date_precision = parse_release_date(year_text)
                chart_tds = tds[1:]  # Chart columns start after Year

            # Skip if already in DB (idempotent re-runs)
            existing = db.query(Release).filter(
                Release.title == title,
                Release.release_type == release_type,
            ).first()
            if existing:
                logger.debug(f"  Skipping existing release: {title}")
                continue

            release = Release(
                title=title,
                release_type=release_type,
                release_date=release_date,
                release_date_precision=release_date_precision,
                label=label,
                formats=formats,
                market="KR",
                artist_id=self.config.artist_id,
                is_verified=True,
                source="wikipedia",
            )
            db.add(release)
            db.flush()  # Get the ID before inserting chart entries

            logger.info(f"    + {release_type}: {title} ({release_date})")

            # Insert chart position entries
            td_values = [clean(td.get_text()) for td in chart_tds]
            for col_idx, chart_name, region in chart_columns:
                # col_idx is relative to all <td> in the row; adjust for the
                # details/year column already consumed above
                adj_idx = col_idx - (1 if use_details_column or tds else 0)
                if 0 <= adj_idx < len(td_values):
                    position = parse_chart_position(td_values[adj_idx])
                    if position is not None:
                        entry = ChartEntry(
                            entity_type="release",
                            release_id=release.id,
                            chart_name=chart_name,
                            chart_region=region,
                            peak_position=position,
                            chart_date=release_date,
                        )
                        db.add(entry)
