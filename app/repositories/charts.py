from __future__ import annotations

from sqlalchemy import func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charts import ChartEntry, ReleaseSales


class ChartRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_entries(
        self,
        chart_name: str | None,
        region: str | None,
        release_id: int | None,
        song_id: int | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[ChartEntry]]:
        q = select(ChartEntry)
        if chart_name:
            q = q.where(ChartEntry.chart_name.ilike(f"%{chart_name}%"))
        if region:
            q = q.where(ChartEntry.chart_region == region)
        if release_id:
            q = q.where(ChartEntry.release_id == release_id)
        if song_id:
            q = q.where(ChartEntry.song_id == song_id)

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(
            q.order_by(nulls_last(ChartEntry.peak_position)).offset(skip).limit(limit)
        )
        items = items_result.scalars().all()
        return total, items

    async def list_sales(
        self,
        release_id: int | None,
        region: str | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[ReleaseSales]]:
        q = select(ReleaseSales)
        if release_id:
            q = q.where(ReleaseSales.release_id == release_id)
        if region:
            q = q.where(ReleaseSales.region == region)

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar()

        items_result = await self.db.execute(
            q.order_by(nulls_last(ReleaseSales.quantity.desc())).offset(skip).limit(limit)
        )
        items = items_result.scalars().all()
        return total, items
