from __future__ import annotations

from sqlalchemy import func, nulls_last
from sqlalchemy.orm import Session

from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Track


class CollaboratorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, name_q: str | None, skip: int, limit: int) -> tuple[int, list[Collaborator]]:
        q = self.db.query(Collaborator)
        if name_q:
            q = q.filter(Collaborator.name.ilike(f"%{name_q}%"))
        total = q.count()
        items = q.order_by(Collaborator.name).offset(skip).limit(limit).all()
        return total, items

    def get(self, collaborator_id: int) -> Collaborator | None:
        return self.db.query(Collaborator).filter(Collaborator.id == collaborator_id).first()

    def get_role_counts(self, collaborator_id: int) -> dict[str, int]:
        rows = (
            self.db.query(SongCredit.role, func.count(SongCredit.id))
            .filter(SongCredit.collaborator_id == collaborator_id)
            .group_by(SongCredit.role)
            .all()
        )
        return {role: count for role, count in rows}

    def list_releases(
        self, collaborator_id: int, skip: int, limit: int
    ) -> tuple[int, list[Release]]:
        q = (
            self.db.query(Release)
            .join(Track, Track.release_id == Release.id)
            .join(SongCredit, SongCredit.song_id == Track.song_id)
            .filter(SongCredit.collaborator_id == collaborator_id)
            .distinct()
        )
        total = q.count()
        items = q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit).all()
        return total, items
