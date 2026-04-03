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

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 12,
                "title": "★★★★★ (5-STAR)",
                "title_korean": "★★★★★",
                "title_romanized": None,
                "release_type": "studio_album",
                "release_date": "2023-06-02",
                "release_date_precision": "day",
                "label": "JYP Entertainment",
                "market": "KR",
                "catalog_number": None,
                "formats": None,
                "artist_id": 1,
                "wikipedia_url": "https://en.wikipedia.org/wiki/5-Star_(Stray_Kids_album)",
                "fandom_url": None,
                "cover_image_url": None,
                "is_verified": True,
                "source": "wikipedia",
                "notes": None,
                "tracks": [
                    {
                        "id": 101,
                        "track_number": 1,
                        "disc_number": 1,
                        "is_title_track": False,
                        "is_intro": False,
                        "is_outro": False,
                        "is_bonus": False,
                        "version_note": None,
                        "song": {
                            "id": 55,
                            "title": "5-Star",
                            "duration_seconds": 213,
                            "spotify_id": "3Qg3S5BytXA5n8rCxJBLYj",
                            "youtube_url": None,
                            "parent_song_id": None,
                            "version_label": None,
                            "credits": []
                        }
                    }
                ]
            }
        }
    }
