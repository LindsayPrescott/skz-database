from datetime import date
from typing import Optional
from pydantic import BaseModel


class ReleaseBase(BaseModel):
    title: str
    title_korean: Optional[str] = None
    title_romanized: Optional[str] = None
    release_type: str
    release_subtype: Optional[str] = None
    release_date: Optional[date] = None
    release_date_precision: str = "day"
    label: Optional[str] = None
    market: str = "KR"
    catalog_number: Optional[str] = None
    formats: Optional[str] = None
    artist_id: Optional[int] = None


class ReleaseResponse(ReleaseBase):
    id: int
    wikipedia_url: Optional[str] = None
    fandom_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_verified: bool = False
    source: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
