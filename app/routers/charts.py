from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants import ChartRegion
from app.database import get_db
from app.repositories import ChartRepository
from app.schemas.charts import ChartEntryResponse, ReleaseSalesResponse
from app.schemas.pagination import Page

router = APIRouter(prefix="/charts", tags=["charts"])


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
    repo = ChartRepository(db)
    total, items = repo.list_entries(chart_name, region, release_id, song_id, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/sales", response_model=Page[ReleaseSalesResponse])
def list_release_sales(
    release_id: int | None = Query(None, description="Filter by release ID"),
    region: str | None = Query(None, description="Filter by region, e.g. 'KR', 'WW'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    repo = ChartRepository(db)
    total, items = repo.list_sales(release_id, region, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)
