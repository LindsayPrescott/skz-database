from __future__ import annotations

from sqlalchemy import func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Track


class CollaboratorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, name_q: str | None, skip: int, limit: int) -> tuple[int, list[Collaborator]]:
        q = select(Collaborator)
        if name_q:
            q = q.where(Collaborator.name.ilike(f"%{name_q}%"))

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(q.order_by(Collaborator.name).offset(skip).limit(limit))
        items = items_result.scalars().all()
        return total, items

    async def get(self, collaborator_id: int) -> Collaborator | None:
        result = await self.db.execute(
            select(Collaborator).where(Collaborator.id == collaborator_id)
        )
        return result.scalar_one_or_none()

    async def get_role_counts(self, collaborator_id: int) -> dict[str, int]:
        result = await self.db.execute(
            select(SongCredit.role, func.count(SongCredit.id))
            .where(SongCredit.collaborator_id == collaborator_id)
            .group_by(SongCredit.role)
        )
        return {role: count for role, count in result.all()}

    async def list_releases(
        self, collaborator_id: int, skip: int, limit: int
    ) -> tuple[int, list[Release]]:
        q = (
            select(Release)
            .join(Track, Track.release_id == Release.id)
            .join(SongCredit, SongCredit.song_id == Track.song_id)
            .where(SongCredit.collaborator_id == collaborator_id)
            .distinct()
        )

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(
            q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit)
        )
        items = items_result.scalars().all()
        return total, items
