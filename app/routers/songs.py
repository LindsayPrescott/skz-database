from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.songs import Song
from app.schemas.pagination import Page
from app.schemas.songs import SongResponse, SongWithCreditsResponse, SongCreditResponse

router = APIRouter(prefix="/songs", tags=["songs"])


ReleaseStatus = Literal["released", "unreleased", "snippet", "stage_only", "predebut", "cover"]


@router.get("/", response_model=Page[SongResponse])
def list_songs(
    status: ReleaseStatus | None = Query(None),
    versions: bool = Query(False, description="Include version songs (parent_song_id is set). Default: canonical songs only."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Song)
    if status:
        q = q.filter(Song.release_status == status)
    if not versions:
        q = q.filter(Song.parent_song_id.is_(None))
    total = q.count()
    items = q.order_by(Song.title).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/search", response_model=Page[SongResponse])
def search_songs(
    q: str = Query(..., min_length=1, description="Search term matched against title fields"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    term = f"%{q}%"
    base_q = db.query(Song).filter(
        Song.title.ilike(term)
        | Song.title_korean.ilike(term)
        | Song.title_romanized.ilike(term)
    )
    total = base_q.count()
    items = base_q.order_by(Song.title).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{song_id}", response_model=SongWithCreditsResponse)
def get_song(song_id: int, db: Session = Depends(get_db)):
    song = (
        db.query(Song)
        .options(joinedload(Song.credits), joinedload(Song.versions))
        .filter(Song.id == song_id)
        .first()
    )
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@router.get("/{song_id}/versions", response_model=list[SongResponse])
def get_song_versions(song_id: int, db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    # Return versions of this song, or versions of its parent if this is itself a version
    parent_id = song.parent_song_id or song.id
    return (
        db.query(Song)
        .filter(Song.parent_song_id == parent_id, Song.id != song_id)
        .order_by(Song.version_label)
        .all()
    )
