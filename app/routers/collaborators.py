from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, nulls_last
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Track
from app.schemas.collaborators import CollaboratorDetailResponse, CollaboratorReleasesPage, CollaboratorResponse
from app.schemas.pagination import Page

router = APIRouter(prefix="/collaborators", tags=["collaborators"])


@router.get("/", response_model=Page[CollaboratorResponse])
def list_collaborators(
    q: str | None = Query(None, min_length=1, description="Search by collaborator name."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Collaborator)
    if q:
        query = query.filter(Collaborator.name.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(Collaborator.name).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{collaborator_id}", response_model=CollaboratorDetailResponse)
def get_collaborator(collaborator_id: int, db: Session = Depends(get_db)):
    collab = db.query(Collaborator).filter(Collaborator.id == collaborator_id).first()
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    roles = {
        role: count
        for role, count in (
            db.query(SongCredit.role, func.count(SongCredit.id))
            .filter(SongCredit.collaborator_id == collaborator_id)
            .group_by(SongCredit.role)
            .all()
        )
    }
    return CollaboratorDetailResponse(
        id=collab.id,
        name=collab.name,
        notes=collab.notes,
        roles=roles,
    )


@router.get("/{collaborator_id}/releases", response_model=CollaboratorReleasesPage)
def get_collaborator_releases(
    collaborator_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Returns releases containing at least one song this collaborator is credited on."""
    collab = db.query(Collaborator).filter(Collaborator.id == collaborator_id).first()
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")

    q = (
        db.query(Release)
        .join(Track, Track.release_id == Release.id)
        .join(SongCredit, SongCredit.song_id == Track.song_id)
        .filter(SongCredit.collaborator_id == collaborator_id)
        .distinct()
    )
    total = q.count()
    items = q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit).all()
    return CollaboratorReleasesPage(
        collaborator=CollaboratorResponse.model_validate(collab),
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + limit < total,
        items=items,
    )
