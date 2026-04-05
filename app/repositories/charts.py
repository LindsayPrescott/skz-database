from __future__ import annotations

from sqlalchemy import nulls_last
from sqlalchemy.orm import Session

from app.models.charts import ChartEntry, ReleaseSales


class ChartRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_entries(
        self,
        chart_name: str | None,
        region: str | None,
        release_id: int | None,
        song_id: int | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[ChartEntry]]:
        q = self.db.query(ChartEntry)
        if chart_name:
            q = q.filter(ChartEntry.chart_name.ilike(f"%{chart_name}%"))
        if region:
            q = q.filter(ChartEntry.chart_region == region)
        if release_id:
            q = q.filter(ChartEntry.release_id == release_id)
        if song_id:
            q = q.filter(ChartEntry.song_id == song_id)
        total = q.count()
        items = q.order_by(nulls_last(ChartEntry.peak_position)).offset(skip).limit(limit).all()
        return total, items

    def list_sales(
        self,
        release_id: int | None,
        region: str | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[ReleaseSales]]:
        q = self.db.query(ReleaseSales)
        if release_id:
            q = q.filter(ReleaseSales.release_id == release_id)
        if region:
            q = q.filter(ReleaseSales.region == region)
        total = q.count()
        items = q.order_by(nulls_last(ReleaseSales.quantity.desc())).offset(skip).limit(limit).all()
        return total, items
