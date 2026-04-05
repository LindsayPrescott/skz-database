from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import CollaboratorRepository
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
    repo = CollaboratorRepository(db)
    total, items = repo.list(q, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{collaborator_id}", response_model=CollaboratorDetailResponse)
def get_collaborator(collaborator_id: int, db: Session = Depends(get_db)):
    repo = CollaboratorRepository(db)
    collab = repo.get(collaborator_id)
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    roles = repo.get_role_counts(collaborator_id)
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
    repo = CollaboratorRepository(db)
    collab = repo.get(collaborator_id)
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    total, items = repo.list_releases(collaborator_id, skip, limit)
    return CollaboratorReleasesPage(
        collaborator=CollaboratorResponse.model_validate(collab),
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + limit < total,
        items=items,
    )
