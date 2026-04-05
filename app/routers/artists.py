from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ArtistType, CreditRole, ReleaseType
from app.database import get_async_db
from app.repositories import ArtistRepository
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
async def list_artists(
    artist_type: list[ArtistType] | None = Query(None, description="Filter by artist type."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
):
    repo = ArtistRepository(db)
    total, items = await repo.list(artist_type, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{artist_id}", response_model=ArtistWithMembersResponse)
async def get_artist(
    artist_id: int,
    include_former: bool = Query(False, description="Include former members in the response."),
    db: AsyncSession = Depends(get_async_db),
):
    repo = ArtistRepository(db)
    artist = await repo.get_with_memberships(artist_id)
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
async def get_artist_releases(
    artist_id: int,
    release_type: list[ReleaseType] | None = Query(None, description="Filter by one or more release types."),
    role: list[CreditRole] | None = Query(None, description="Filter to releases where this artist has a specific credit role."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Returns releases attributed to this artist OR containing a song they are
    credited on (lyricist, composer, arranger, vocalist).
    """
    repo = ArtistRepository(db)
    artist = await repo.get(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    total, items = await repo.list_releases(artist_id, release_type, role, skip, limit)
    return ArtistReleasesPage(
        artist=ArtistResponse.model_validate(artist),
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + limit < total,
        items=items,
    )


@router.get("/{artist_id}/credits", response_model=ArtistCreditsPage)
async def get_artist_credits(
    artist_id: int,
    role: list[CreditRole] | None = Query(None, description="Filter by credit role."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
):
    """All songs this artist has a writing or production credit on."""
    repo = ArtistRepository(db)
    artist = await repo.get(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    total, rows = await repo.list_credits(artist_id, role, skip, limit)
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
async def get_artist_collaborators(
    artist_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """Ranked list of artists and collaborators most frequently co-credited with this artist."""
    repo = ArtistRepository(db)
    artist = await repo.get(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    co_artists, co_collaborators = await repo.get_collaborators(artist_id)
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
