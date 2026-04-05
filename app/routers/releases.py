from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.constants import Market, ReleaseType
from app.database import get_db
from app.repositories import ReleaseRepository
from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse, ReleaseWithTracksResponse
from app.schemas.tracks import TrackSummaryResponse, TrackResponse

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/", response_model=Page[ReleaseResponse])
def list_releases(
    release_type: list[ReleaseType] | None = Query(None),
    market: list[Market] | None = Query(None),
    artist_id: int | None = Query(None, description="Filter by artist ID."),
    year_from: int | None = Query(None, ge=2017, description="Filter releases from this year (inclusive)"),
    year_to: int | None = Query(None, ge=2017, description="Filter releases up to this year (inclusive)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    repo = ReleaseRepository(db)
    total, items = repo.list(release_type, market, artist_id, year_from, year_to, skip, limit)
    return Page(total=total, skip=skip, limit=limit, has_more=skip + limit < total, items=items)


@router.get("/{release_id}", response_model=ReleaseWithTracksResponse)
def get_release(
    release_id: int,
    tracks: Literal["summary", "full"] | None = Query(
        None,
        description=(
            "Include an inline tracklist. "
            "`summary` returns `{track_number, disc_number, is_title_track, version_note, song: {id, title, duration_seconds}}`. "
            "`full` returns all track flags plus the complete nested song (all fields + credits). "
            "Omit to return release metadata only."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Get a single release by ID.

    **`?tracks` values:**

    | Value | Track shape |
    |---|---|
    | *(omitted)* | No tracks returned |
    | `summary` | `track_number`, `disc_number`, `is_title_track`, `version_note`, `song: {id, title, duration_seconds}` |
    | `full` | All track flags + complete nested `song` (all fields including `credits`) |

    The response schema below documents the **`full`** shape.
    `summary` returns a subset of each track's `song` object.
    """
    repo = ReleaseRepository(db)

    if tracks is None:
        release = repo.get(release_id)
        if not release:
            raise HTTPException(status_code=404, detail="Release not found")
        return ReleaseWithTracksResponse.model_validate(release)

    release = repo.get_with_tracks(release_id, full=(tracks == "full"))
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    sorted_tracks = sorted(release.tracks, key=lambda t: (t.disc_number or 1, t.track_number or 0))

    if tracks == "summary":
        track_data = [TrackSummaryResponse.model_validate(t) for t in sorted_tracks]
    else:
        track_data = [TrackResponse.model_validate(t) for t in sorted_tracks]

    result = ReleaseWithTracksResponse.model_validate(release)
    result.tracks = track_data
    return result
