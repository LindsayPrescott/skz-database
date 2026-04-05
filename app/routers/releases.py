from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.constants import Market, ReleaseType
from app.database import get_db
from app.repositories import ReleaseRepository
from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse
from app.schemas.tracks import TrackSummaryResponse, TrackResponse

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/", response_model=Page[ReleaseResponse])
def list_releases(
    release_type: list[ReleaseType] | None = Query(None),
    market: list[Market] | None = Query(None),
    artist_id: int | None = Query(None, description="Filter by artist ID."),
    year_from: int | None = Query(None, ge=2017, description="Filter releases from this year (inclusive)"),
    year_to: int | None = Query(None, ge=2017, description="Filter releases up to this year (inclusive)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    repo = ReleaseRepository(db)
    total, items = repo.list(release_type, market, artist_id, year_from, year_to, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{release_id}", response_model=ReleaseResponse)
def get_release(release_id: int, db: Session = Depends(get_db)):
    release = ReleaseRepository(db).get(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.get("/{release_id}/tracks", response_model=list[TrackResponse])
def get_release_tracks(release_id: int, db: Session = Depends(get_db)):
    release = ReleaseRepository(db).get_with_tracks(release_id, full=True)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return sorted(release.tracks, key=lambda t: (t.disc_number or 1, t.track_number or 0))


@router.get("/{release_id}/tracks/summary", response_model=list[TrackSummaryResponse])
def get_release_tracks_summary(release_id: int, db: Session = Depends(get_db)):
    release = ReleaseRepository(db).get_with_tracks(release_id, full=False)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return sorted(release.tracks, key=lambda t: (t.disc_number or 1, t.track_number or 0))
