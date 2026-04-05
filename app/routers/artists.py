from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.artists import Artist, ArtistMember
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Track
from app.schemas.artists import ArtistReleasesPage, ArtistResponse, ArtistWithMembersResponse
from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse

router = APIRouter(prefix="/artists", tags=["artists"])

ReleaseType = Literal[
    "studio_album", "ep", "single_album", "compilation_album",
    "repackage", "mixtape", "digital_single", "feature",
    "skz_record", "skz_player",
]

CreditRole = Literal[
    "vocalist", "rapper", "featured", "lyricist", "composer",
    "arranger", "producer", "executive_producer",
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
def get_artist(
    artist_id: int,
    include_former: bool = Query(False, description="Include former members in the response."),
    db: Session = Depends(get_db),
):
    artist = (
        db.query(Artist)
        .options(
            joinedload(Artist.memberships).joinedload(ArtistMember.child),
            joinedload(Artist.member_of).joinedload(ArtistMember.parent),
        )
        .filter(Artist.id == artist_id)
        .first()
    )
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    result = ArtistWithMembersResponse.model_validate(artist)
    result.members = [
        ArtistResponse.model_validate(m.child)
        for m in artist.memberships
        if include_former or not m.child.is_former_member
    ]
    result.groups = [
        ArtistResponse.model_validate(m.parent)
        for m in artist.member_of
    ]
    return result


@router.get("/{artist_id}/releases", response_model=ArtistReleasesPage)
def get_artist_releases(
    artist_id: int,
    release_type: list[ReleaseType] | None = Query(
        None,
        description="Filter by one or more release types.",
    ),
    role: list[CreditRole] | None = Query(
        None,
        description="Filter to releases where this artist has a specific credit role.",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Returns releases attributed to this artist OR containing a song they are
    credited on (lyricist, composer, arranger, vocalist).

    - For the group (Stray Kids): returns all releases where `Release.artist_id == 1`.
    - For individual members: also includes releases they contributed credits to,
      even if the release is attributed to the group or another artist.
    - Use `?role=composer` (or multiple) to restrict to releases where this artist
      holds a specific credit role.
    """
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    credited_release_ids = (
        db.query(Track.release_id)
        .join(SongCredit, SongCredit.song_id == Track.song_id)
        .filter(SongCredit.artist_id == artist_id)
    )

    if role:
        credited_release_ids = credited_release_ids.filter(SongCredit.role.in_(role))

    q = (
        db.query(Release)
        .filter(
            or_(
                Release.artist_id == artist_id,
                Release.id.in_(credited_release_ids),
            )
        )
        .distinct()
    )

    if release_type:
        q = q.filter(Release.release_type.in_(release_type))

    total = q.count()
    items = q.order_by(Release.release_date.desc()).offset(skip).limit(limit).all()
    return ArtistReleasesPage(
        artist=ArtistResponse.model_validate(artist),
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + limit < total,
        items=items,
    )
