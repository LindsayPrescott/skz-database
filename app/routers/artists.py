from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.artists import Artist, ArtistMember
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Track
from app.schemas.artists import ArtistResponse, ArtistWithMembersResponse
from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse

router = APIRouter(prefix="/artists", tags=["artists"])

ReleaseType = Literal[
    "studio_album", "ep", "single_album", "compilation_album",
    "repackage", "mixtape", "digital_single", "feature",
    "skz_record", "skz_player",
]


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
    artist = (
        db.query(Artist)
        .options(joinedload(Artist.memberships).joinedload(ArtistMember.child))
        .filter(Artist.id == artist_id)
        .first()
    )
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    result = ArtistWithMembersResponse.model_validate(artist)
    result.members = [
        ArtistResponse.model_validate(m.child) for m in artist.memberships
    ]
    return result


@router.get("/{artist_id}/releases", response_model=Page[ReleaseResponse])
def get_artist_releases(
    artist_id: int,
    release_type: list[ReleaseType] | None = Query(
        None,
        description="Filter by one or more release types.",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Returns releases containing at least one song this artist is credited on
    (as lyricist, composer, arranger, or vocalist).

    Works for groups and individual members alike — for a member like Woojin
    this returns only the releases from his time in the group; for Bang Chan
    it returns all releases he contributed to including solo and unit work.
    """
    if not db.query(Artist).filter(Artist.id == artist_id).first():
        raise HTTPException(status_code=404, detail="Artist not found")

    q = (
        db.query(Release)
        .join(Track, Track.release_id == Release.id)
        .join(SongCredit, SongCredit.song_id == Track.song_id)
        .filter(SongCredit.artist_id == artist_id)
        .distinct()
    )

    if release_type:
        q = q.filter(Release.release_type.in_(release_type))

    total = q.count()
    items = q.order_by(Release.release_date.desc()).offset(skip).limit(limit).all()
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)
