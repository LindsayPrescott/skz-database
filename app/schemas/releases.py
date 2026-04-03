from datetime import date
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.tracks import TrackResponse


class ReleaseBase(BaseModel):
    title: str
    title_korean: Optional[str] = None
    title_romanized: Optional[str] = None
    release_type: str
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


class ReleaseWithTracksResponse(ReleaseResponse):
    """
    Release with an inline `tracks` array. Shape of each track depends on
    the `?tracks=` parameter used to request this response:

    - `summary` — each track contains `{track_number, disc_number,
      is_title_track, version_note, song: {id, title, duration_seconds}}`
    - `full` — each track contains all flags plus a complete nested `song`
      object (all song fields including `credits`)

    The schema below documents the **full** shape.
    """
    tracks: list[TrackResponse] = Field(
        default=[],
        description=(
            "Inline tracklist. Empty unless ?tracks=summary or ?tracks=full is used. "
            "summary shape: {track_number, disc_number, is_title_track, version_note, song: {id, title, duration_seconds}}. "
            "full shape: all track flags + complete nested song with credits."
        ),
    )
