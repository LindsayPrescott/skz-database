from datetime import date
from typing import Optional
from pydantic import BaseModel

from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse
from app.schemas.songs import SongResponse


class ArtistBase(BaseModel):
    name: str
    name_korean: Optional[str] = None
    name_romanized: Optional[str] = None
    artist_type: str
    birth_name: Optional[str] = None
    birth_name_korean: Optional[str] = None
    birth_date: Optional[date] = None
    nationality: Optional[str] = None
    is_former_member: bool = False


class ArtistResponse(ArtistBase):
    id: int
    spotify_id: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class ArtistReleasesPage(Page[ReleaseResponse]):
    artist: ArtistResponse


class ArtistCreditItem(BaseModel):
    song: SongResponse
    role: str


class ArtistCreditsPage(Page[ArtistCreditItem]):
    artist: ArtistResponse


class ArtistCollaboratorItem(BaseModel):
    id: int
    name: str
    type: str  # "artist" | "collaborator"
    co_credit_count: int


class ArtistCollaboratorsResponse(BaseModel):
    artist: ArtistResponse
    collaborators: list[ArtistCollaboratorItem]


class ArtistWithMembersResponse(ArtistResponse):
    """Artist response with nested member list (used for units/groups).

    By default `members` contains only current members. Pass `?include_former=true`
    to also include former members (e.g. Woojin with `is_former_member=true`).
    `groups` lists the groups/units this artist belongs to.
    """
    members: list[ArtistResponse] = []
    groups: list[ArtistResponse] = []
