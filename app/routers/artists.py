from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, nulls_last, or_
from sqlalchemy.orm import Session, joinedload

from app.constants import ArtistType, CreditRole, ReleaseType
from app.database import get_db
from app.models.artists import Artist, ArtistMember
from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track
from app.schemas.artists import (
    ArtistCollaboratorsResponse,
    ArtistCollaboratorItem,
    ArtistCreditItem,
    ArtistCreditsPage,
    ArtistReleasesPage,
    ArtistResponse,
    ArtistWithMembersResponse,
)
from app.schemas.pagination import Page
from app.schemas.songs import SongResponse

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/", response_model=Page[ArtistResponse])
def list_artists(
    artist_type: list[ArtistType] | None = Query(None, description="Filter by artist type."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Artist)
    if artist_type:
        q = q.filter(Artist.artist_type.in_(artist_type))
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
      holds that specific credit role. When role is provided, only credited releases
      are returned — group-attributed releases are excluded.
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
            .filter(Release.id.in_(credited_release_ids))
            .distinct()
        )
    else:
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
    items = q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit).all()
    return ArtistReleasesPage(
        artist=ArtistResponse.model_validate(artist),
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + limit < total,
        items=items,
    )


@router.get("/{artist_id}/credits", response_model=ArtistCreditsPage)
def get_artist_credits(
    artist_id: int,
    role: list[CreditRole] | None = Query(None, description="Filter by credit role."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """All songs this artist has a writing or production credit on."""
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    q = (
        db.query(Song, SongCredit.role)
        .join(SongCredit, SongCredit.song_id == Song.id)
        .filter(SongCredit.artist_id == artist_id)
    )
    if role:
        q = q.filter(SongCredit.role.in_(role))

    total = q.count()
    rows = q.order_by(Song.title).offset(skip).limit(limit).all()
    return ArtistCreditsPage(
        artist=ArtistResponse.model_validate(artist),
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + limit < total,
        items=[
            ArtistCreditItem(song=SongResponse.model_validate(song), role=credit_role)
            for song, credit_role in rows
        ],
    )


@router.get("/{artist_id}/collaborators", response_model=ArtistCollaboratorsResponse)
def get_artist_collaborators(
    artist_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Ranked list of artists and collaborators most frequently co-credited with this artist."""
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    artist_song_ids = (
        db.query(SongCredit.song_id)
        .filter(SongCredit.artist_id == artist_id)
        .distinct()
        .subquery()
    )

    co_artists = (
        db.query(Artist.id, Artist.name, func.count(SongCredit.id).label("count"))
        .join(SongCredit, SongCredit.artist_id == Artist.id)
        .filter(SongCredit.song_id.in_(artist_song_ids), Artist.id != artist_id)
        .group_by(Artist.id, Artist.name)
        .all()
    )

    co_collaborators = (
        db.query(Collaborator.id, Collaborator.name, func.count(SongCredit.id).label("count"))
        .join(SongCredit, SongCredit.collaborator_id == Collaborator.id)
        .filter(SongCredit.song_id.in_(artist_song_ids))
        .group_by(Collaborator.id, Collaborator.name)
        .all()
    )

    combined = sorted(
        [ArtistCollaboratorItem(id=r.id, name=r.name, type="artist", co_credit_count=r.count)
         for r in co_artists] +
        [ArtistCollaboratorItem(id=r.id, name=r.name, type="collaborator", co_credit_count=r.count)
         for r in co_collaborators],
        key=lambda x: x.co_credit_count,
        reverse=True,
    )[:limit]

    return ArtistCollaboratorsResponse(
        artist=ArtistResponse.model_validate(artist),
        collaborators=combined,
    )
