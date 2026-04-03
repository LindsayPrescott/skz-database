from typing import Optional
from pydantic import BaseModel

from app.schemas.songs import SongResponse, SongWithCreditsResponse


class SongMinimalResponse(BaseModel):
    """Minimal song shape used inside summary track listings."""
    id: int
    title: str
    duration_seconds: Optional[int] = None

    model_config = {"from_attributes": True}


class TrackSummaryResponse(BaseModel):
    """
    Lean track shape — enough to render a track listing (e.g. album back cover).
    Returned when `?tracks=summary`.
    """
    track_number: Optional[int] = None
    disc_number: int = 1
    is_title_track: bool = False
    version_note: Optional[str] = None
    song: SongMinimalResponse

    model_config = {"from_attributes": True}


class TrackResponse(BaseModel):
    """
    Full track shape with all flags and complete nested song.
    Returned when `?tracks=full`.
    """
    id: int
    release_id: int
    song_id: int
    track_number: Optional[int] = None
    disc_number: int = 1
    is_title_track: bool = False
    is_intro: bool = False
    is_outro: bool = False
    is_bonus: bool = False
    version_note: Optional[str] = None
    song: SongWithCreditsResponse

    model_config = {"from_attributes": True}
