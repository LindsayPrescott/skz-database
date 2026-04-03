from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.releases import Release
from app.schemas.releases import ReleaseResponse
from app.schemas.tracks import TrackResponse

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/", response_model=list[ReleaseResponse])
def list_releases(
    release_type: str | None = Query(None, description="Filter by type, e.g. 'ep', 'studio_album'"),
    market: str | None = Query(None, description="Filter by market, e.g. 'KR', 'JP'"),
    db: Session = Depends(get_db),
):
    q = db.query(Release)
    if release_type:
        q = q.filter(Release.release_type == release_type)
    if market:
        q = q.filter(Release.market == market)
    return q.order_by(Release.release_date.desc()).all()


@router.get("/{release_id}", response_model=ReleaseResponse)
def get_release(release_id: int, db: Session = Depends(get_db)):
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.get("/{release_id}/tracks", response_model=list[TrackResponse])
def get_release_tracks(release_id: int, db: Session = Depends(get_db)):
    release = (
        db.query(Release)
        .options(joinedload(Release.tracks))
        .filter(Release.id == release_id)
        .first()
    )
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return sorted(release.tracks, key=lambda t: (t.disc_number or 1, t.track_number or 0))
