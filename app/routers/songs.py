from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.constants import Language, ReleaseStatus
from app.database import get_db
from app.repositories import SongRepository
from app.schemas.pagination import Page
from app.schemas.songs import SongResponse, SongVersionsResponse, SongWithCreditsResponse

router = APIRouter(prefix="/songs", tags=["songs"])


@router.get("/", response_model=Page[SongResponse])
def list_songs(
    status: ReleaseStatus | None = Query(None),
    language: list[Language] | None = Query(None, description="Filter by language."),
    versions: bool = Query(False, description="Include version songs (parent_song_id is set). Default: canonical songs only."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    repo = SongRepository(db)
    total, items = repo.list(status, language, versions, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/search", response_model=Page[SongResponse])
def search_songs(
    q: str = Query(..., min_length=1, description="Search term matched against title fields"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    repo = SongRepository(db)
    total, items = repo.search(q, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{song_id}", response_model=SongWithCreditsResponse)
def get_song(song_id: int, db: Session = Depends(get_db)):
    repo = SongRepository(db)
    song = repo.get_with_credits(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@router.get("/{song_id}/versions", response_model=SongVersionsResponse)
def get_song_versions(song_id: int, db: Session = Depends(get_db)):
    repo = SongRepository(db)
    original, versions = repo.get_version_family(song_id)
    if not original:
        raise HTTPException(status_code=404, detail="Song not found")
    return SongVersionsResponse(
        original=SongResponse.model_validate(original),
        versions=[SongResponse.model_validate(v) for v in versions],
    )
