from datetime import date
from typing import Optional
from pydantic import BaseModel


class ArtistMemberResponse(BaseModel):
    parent_artist_id: int
    child_artist_id: int

    model_config = {"from_attributes": True}


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


class ArtistWithMembersResponse(ArtistResponse):
    """Artist response with nested member list (used for units/group)."""
    memberships: list[ArtistMemberResponse] = []
