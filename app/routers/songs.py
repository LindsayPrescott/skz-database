from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.songs import Song
from app.schemas.songs import SongResponse, SongWithCreditsResponse

router = APIRouter(prefix="/songs", tags=["songs"])


@router.get("/", response_model=list[SongResponse])
def list_songs(
    status: str | None = Query(None, description="Filter by release_status, e.g. 'unreleased', 'released'"),
    db: Session = Depends(get_db),
):
    q = db.query(Song)
    if status:
        q = q.filter(Song.release_status == status)
    return q.order_by(Song.title).all()


@router.get("/search", response_model=list[SongResponse])
def search_songs(
    q: str = Query(..., min_length=1, description="Search term matched against title fields"),
    db: Session = Depends(get_db),
):
    term = f"%{q}%"
    return (
        db.query(Song)
        .filter(
            Song.title.ilike(term)
            | Song.title_korean.ilike(term)
            | Song.title_romanized.ilike(term)
        )
        .order_by(Song.title)
        .all()
    )


@router.get("/{song_id}", response_model=SongWithCreditsResponse)
def get_song(song_id: int, db: Session = Depends(get_db)):
    song = (
        db.query(Song)
        .options(joinedload(Song.credits))
        .filter(Song.id == song_id)
        .first()
    )
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song
