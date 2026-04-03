from typing import Optional
from pydantic import BaseModel

from app.schemas.songs import SongResponse


class TrackResponse(BaseModel):
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
    song: SongResponse

    model_config = {"from_attributes": True}
