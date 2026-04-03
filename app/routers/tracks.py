from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.songs import Track
from app.schemas.tracks import TrackResponse

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.get("/{track_id}", response_model=TrackResponse)
def get_track(track_id: int, db: Session = Depends(get_db)):
    track = (
        db.query(Track)
        .options(joinedload(Track.song))
        .filter(Track.id == track_id)
        .first()
    )
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track
