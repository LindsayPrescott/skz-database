from __future__ import annotations

from sqlalchemy import func, nulls_last, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.artists import Artist, ArtistMember
from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track


class ArtistRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self, artist_type: list[str] | None, skip: int, limit: int
    ) -> tuple[int, list[Artist]]:
        q = select(Artist)
        if artist_type:
            q = q.where(Artist.artist_type.in_(artist_type))

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(q.order_by(Artist.id).offset(skip).limit(limit))
        items = items_result.scalars().all()
        return total, items

    async def get_with_memberships(self, artist_id: int) -> Artist | None:
        result = await self.db.execute(
            select(Artist)
            .options(
                joinedload(Artist.memberships).joinedload(ArtistMember.child),
                joinedload(Artist.member_of).joinedload(ArtistMember.parent),
            )
            .where(Artist.id == artist_id)
        )
        return result.unique().scalar_one_or_none()

    async def get(self, artist_id: int) -> Artist | None:
        result = await self.db.execute(select(Artist).where(Artist.id == artist_id))
        return result.scalar_one_or_none()

    async def list_releases(
        self,
        artist_id: int,
        release_type: list[str] | None,
        role: list[str] | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Release]]:
        credited_subq = (
            select(Track.release_id)
            .join(SongCredit, SongCredit.song_id == Track.song_id)
            .where(SongCredit.artist_id == artist_id)
        )
        if role:
            credited_subq = credited_subq.where(SongCredit.role.in_(role))
        credited_subq = credited_subq.scalar_subquery()

        if role:
            q = select(Release).where(Release.id.in_(credited_subq)).distinct()
        else:
            q = (
                select(Release)
                .where(or_(Release.artist_id == artist_id, Release.id.in_(credited_subq)))
                .distinct()
            )
        if release_type:
            q = q.where(Release.release_type.in_(release_type))

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(
            q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit)
        )
        items = items_result.scalars().all()
        return total, items

    async def list_credits(
        self,
        artist_id: int,
        role: list[str] | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[tuple[Song, str]]]:
        q = (
            select(Song, SongCredit.role)
            .join(SongCredit, SongCredit.song_id == Song.id)
            .where(SongCredit.artist_id == artist_id)
        )
        if role:
            q = q.where(SongCredit.role.in_(role))

        count_q = select(func.count(Song.id)).join(
            SongCredit, SongCredit.song_id == Song.id
        ).where(SongCredit.artist_id == artist_id)
        if role:
            count_q = count_q.where(SongCredit.role.in_(role))
        total_result = await self.db.execute(count_q)
        total = total_result.scalar()

        items_result = await self.db.execute(
            q.order_by(Song.title).offset(skip).limit(limit)
        )
        rows = items_result.all()
        return total, rows

    async def get_collaborators(self, artist_id: int) -> tuple[list, list]:
        artist_song_ids = (
            select(SongCredit.song_id)
            .where(SongCredit.artist_id == artist_id)
            .distinct()
            .subquery()
        )

        co_artists_result = await self.db.execute(
            select(Artist.id, Artist.name, func.count(SongCredit.id).label("count"))
            .join(SongCredit, SongCredit.artist_id == Artist.id)
            .where(SongCredit.song_id.in_(select(artist_song_ids.c.song_id)), Artist.id != artist_id)
            .group_by(Artist.id, Artist.name)
        )
        co_artists = co_artists_result.all()

        co_collaborators_result = await self.db.execute(
            select(Collaborator.id, Collaborator.name, func.count(SongCredit.id).label("count"))
            .join(SongCredit, SongCredit.collaborator_id == Collaborator.id)
            .where(SongCredit.song_id.in_(select(artist_song_ids.c.song_id)))
            .group_by(Collaborator.id, Collaborator.name)
        )
        co_collaborators = co_collaborators_result.all()

        return co_artists, co_collaborators
