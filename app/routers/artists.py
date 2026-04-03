from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.artists import Artist
from app.schemas.artists import ArtistResponse, ArtistWithMembersResponse

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/", response_model=list[ArtistResponse])
def list_artists(db: Session = Depends(get_db)):
    return db.query(Artist).all()


@router.get("/{artist_id}", response_model=ArtistWithMembersResponse)
def get_artist(artist_id: int, db: Session = Depends(get_db)):
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist


@router.get("/{artist_id}/releases")
def get_artist_releases(artist_id: int, db: Session = Depends(get_db)):
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist.releases
