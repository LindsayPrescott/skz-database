from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.models.credits import SongCredit
from app.models.songs import Song


class SongRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        status: str | None,
        language: list[str] | None,
        include_versions: bool,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Song]]:
        q = self.db.query(Song)
        if status:
            q = q.filter(Song.release_status == status)
        if language:
            q = q.filter(Song.language.in_(language))
        if not include_versions:
            q = q.filter(Song.parent_song_id.is_(None))
        total = q.count()
        items = q.order_by(Song.title).offset(skip).limit(limit).all()
        return total, items

    def search(self, term: str, skip: int, limit: int) -> tuple[int, list[Song]]:
        pattern = f"%{term}%"
        q = self.db.query(Song).filter(
            Song.title.ilike(pattern)
            | Song.title_korean.ilike(pattern)
            | Song.title_romanized.ilike(pattern)
            | Song.title_japanese.ilike(pattern)
        )
        total = q.count()
        items = q.order_by(Song.title).offset(skip).limit(limit).all()
        return total, items

    def get_with_credits(self, song_id: int) -> Song | None:
        return (
            self.db.query(Song)
            .options(
                joinedload(Song.credits).joinedload(SongCredit.artist),
                joinedload(Song.credits).joinedload(SongCredit.collaborator),
                joinedload(Song.versions),
            )
            .filter(Song.id == song_id)
            .first()
        )

    def get_version_family(self, song_id: int) -> tuple[Song | None, list[Song]]:
        song = self.db.query(Song).filter(Song.id == song_id).first()
        if not song:
            return None, []
        parent_id = song.parent_song_id or song.id
        original = self.db.query(Song).filter(Song.id == parent_id).first()
        versions = (
            self.db.query(Song)
            .filter(Song.parent_song_id == parent_id)
            .order_by(Song.version_label)
            .all()
        )
        return original, versions
