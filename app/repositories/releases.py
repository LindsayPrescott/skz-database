from __future__ import annotations

from sqlalchemy import extract, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, subqueryload

from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track


class ReleaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        release_type: list[str] | None,
        market: list[str] | None,
        artist_id: int | None,
        year_from: int | None,
        year_to: int | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Release]]:
        q = select(Release)
        if release_type:
            q = q.where(Release.release_type.in_(release_type))
        if market:
            q = q.where(Release.market.in_(market))
        if artist_id is not None:
            q = q.where(Release.artist_id == artist_id)
        if year_from:
            q = q.where(extract("year", Release.release_date) >= year_from)
        if year_to:
            q = q.where(extract("year", Release.release_date) <= year_to)

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(
            q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit)
        )
        items = items_result.scalars().all()
        return total, items

    async def get(self, release_id: int) -> Release | None:
        result = await self.db.execute(select(Release).where(Release.id == release_id))
        return result.scalar_one_or_none()

    async def get_with_tracks(self, release_id: int, full: bool) -> Release | None:
        if full:
            options = [
                joinedload(Release.tracks).joinedload(Track.song).subqueryload(Song.credits).joinedload(SongCredit.artist),
                joinedload(Release.tracks).joinedload(Track.song).subqueryload(Song.credits).joinedload(SongCredit.collaborator),
                joinedload(Release.tracks).joinedload(Track.song).subqueryload(Song.versions),
            ]
        else:
            options = [joinedload(Release.tracks).joinedload(Track.song)]

        result = await self.db.execute(
            select(Release).options(*options).where(Release.id == release_id)
        )
        return result.unique().scalar_one_or_none()
