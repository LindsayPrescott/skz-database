from typing import Optional
from pydantic import BaseModel


class SongCreditResponse(BaseModel):
    id: int
    artist_id: Optional[int] = None
    credit_name_raw: Optional[str] = None
    role: str
    is_primary: bool = True
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class SongBase(BaseModel):
    title: str
    title_korean: Optional[str] = None
    title_romanized: Optional[str] = None
    title_japanese: Optional[str] = None
    duration_seconds: Optional[int] = None
    language: str = "ko"
    has_korean_ver: bool = False
    has_english_ver: bool = False
    has_japanese_ver: bool = False
    release_status: str = "released"
    is_instrumental: bool = False
    original_artist: Optional[str] = None


class SongResponse(SongBase):
    id: int
    spotify_id: Optional[str] = None
    isrc: Optional[str] = None
    wikipedia_url: Optional[str] = None
    fandom_url: Optional[str] = None
    is_verified: bool = False
    source: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class SongWithCreditsResponse(SongResponse):
    credits: list[SongCreditResponse] = []
