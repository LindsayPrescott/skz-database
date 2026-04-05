from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.credits import SongCredit
from app.models.songs import Song


class SongRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        status: str | None,
        language: list[str] | None,
        include_versions: bool,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Song]]:
        q = select(Song)
        if status:
            q = q.where(Song.release_status == status)
        if language:
            q = q.where(Song.language.in_(language))
        if not include_versions:
            q = q.where(Song.parent_song_id.is_(None))

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(q.order_by(Song.title).offset(skip).limit(limit))
        items = items_result.scalars().all()
        return total, items

    async def search(self, term: str, skip: int, limit: int) -> tuple[int, list[Song]]:
        pattern = f"%{term}%"
        q = select(Song).where(
            or_(
                Song.title.ilike(pattern),
                Song.title_korean.ilike(pattern),
                Song.title_romanized.ilike(pattern),
                Song.title_japanese.ilike(pattern),
            )
        )

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(q.order_by(Song.title).offset(skip).limit(limit))
        items = items_result.scalars().all()
        return total, items

    async def get_with_credits(self, song_id: int) -> Song | None:
        result = await self.db.execute(
            select(Song)
            .options(
                joinedload(Song.credits).joinedload(SongCredit.artist),
                joinedload(Song.credits).joinedload(SongCredit.collaborator),
                joinedload(Song.versions),
            )
            .where(Song.id == song_id)
        )
        return result.unique().scalar_one_or_none()

    async def get_version_family(self, song_id: int) -> tuple[Song | None, list[Song]]:
        # First query: resolve the parent ID (need the song's own parent_song_id to know it).
        song_result = await self.db.execute(select(Song).where(Song.id == song_id))
        song = song_result.scalar_one_or_none()
        if not song:
            return None, []

        parent_id = song.parent_song_id or song.id

        # Second query: fetch the whole family in one round-trip, split in Python.
        family_result = await self.db.execute(
            select(Song)
            .where(or_(Song.id == parent_id, Song.parent_song_id == parent_id))
            .order_by(Song.version_label)
        )
        family = family_result.scalars().all()

        original = next((s for s in family if s.id == parent_id), None)
        versions = [s for s in family if s.id != parent_id]
        return original, versions
