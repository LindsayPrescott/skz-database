from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Track
from app.schemas.collaborators import CollaboratorResponse
from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse

router = APIRouter(prefix="/collaborators", tags=["collaborators"])


@router.get("/", response_model=Page[CollaboratorResponse])
def list_collaborators(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Collaborator).order_by(Collaborator.name)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{collaborator_id}", response_model=CollaboratorResponse)
def get_collaborator(collaborator_id: int, db: Session = Depends(get_db)):
    collab = db.query(Collaborator).filter(Collaborator.id == collaborator_id).first()
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    return collab


@router.get("/{collaborator_id}/releases", response_model=Page[ReleaseResponse])
def get_collaborator_releases(
    collaborator_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Returns releases containing at least one song this collaborator is credited on."""
    if not db.query(Collaborator).filter(Collaborator.id == collaborator_id).first():
        raise HTTPException(status_code=404, detail="Collaborator not found")

    q = (
        db.query(Release)
        .join(Track, Track.release_id == Release.id)
        .join(SongCredit, SongCredit.song_id == Track.song_id)
        .filter(SongCredit.collaborator_id == collaborator_id)
        .distinct()
    )
    total = q.count()
    items = q.order_by(Release.release_date.desc()).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)
