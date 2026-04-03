from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.charts import ChartEntry, ReleaseSales
from app.schemas.charts import ChartEntryResponse, ReleaseSalesResponse
from app.schemas.pagination import Page

router = APIRouter(prefix="/charts", tags=["charts"])

ChartRegion = Literal["KR", "JP", "US", "AU", "CA", "FR", "DE", "NZ", "UK", "GLOBAL"]


@router.get("/", response_model=Page[ChartEntryResponse])
def list_chart_entries(
    chart_name: str | None = Query(None, description="Filter by chart name, e.g. 'Billboard 200'"),
    region: ChartRegion | None = Query(None),
    release_id: int | None = Query(None, description="Filter by release ID"),
    song_id: int | None = Query(None, description="Filter by song ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(ChartEntry)
    if chart_name:
        q = q.filter(ChartEntry.chart_name.ilike(f"%{chart_name}%"))
    if region:
        q = q.filter(ChartEntry.chart_region == region)
    if release_id:
        q = q.filter(ChartEntry.release_id == release_id)
    if song_id:
        q = q.filter(ChartEntry.song_id == song_id)
    total = q.count()
    items = q.order_by(ChartEntry.peak_position).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/sales", response_model=Page[ReleaseSalesResponse])
def list_release_sales(
    release_id: int | None = Query(None, description="Filter by release ID"),
    region: str | None = Query(None, description="Filter by region, e.g. 'KR', 'WW'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(ReleaseSales)
    if release_id:
        q = q.filter(ReleaseSales.release_id == release_id)
    if region:
        q = q.filter(ReleaseSales.region == region)
    total = q.count()
    items = q.order_by(ReleaseSales.release_id).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)
