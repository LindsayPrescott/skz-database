from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.artists import Artist
from app.schemas.artists import ArtistResponse, ArtistWithMembersResponse
from app.schemas.pagination import Page

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/", response_model=Page[ArtistResponse])
def list_artists(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Artist)
    total = q.count()
    items = q.order_by(Artist.id).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


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
