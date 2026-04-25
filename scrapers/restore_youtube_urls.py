"""
One-time utility: restore youtube_url values from backup after a DB reset.

Reads data/youtube_urls_backup.json (title → url) and applies each URL
to the matching song row by exact title match.

Run after phases 1–5 complete and before resuming Phase 6 (YouTube scraper).
"""
import json
import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.songs import Song

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BACKUP_FILE = "data/youtube_urls_backup.json"


def restore(db: Session) -> None:
    with open(BACKUP_FILE, encoding="utf-8") as f:
        backup: dict[str, str] = json.load(f)

    restored = 0
    not_found = []

    for title, url in backup.items():
        song = db.query(Song).filter(Song.title == title).first()
        if song:
            song.youtube_url = url
            restored += 1
        else:
            not_found.append(title)

    db.commit()
    logger.info(f"Restored: {restored} | Not found: {len(not_found)}")
    if not_found:
        logger.warning("Songs not found in DB (may need manual review):")
        for t in not_found:
            logger.warning(f"  {t}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        restore(db)
    finally:
        db.close()
