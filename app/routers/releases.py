from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.database import get_db
from app.models.releases import Release
from app.schemas.pagination import Page
from app.schemas.releases import ReleaseResponse, ReleaseWithTracksResponse
from app.schemas.tracks import TrackSummaryResponse, TrackResponse

router = APIRouter(prefix="/releases", tags=["releases"])


ReleaseType = Literal[
    "studio_album", "ep", "single_album", "compilation_album",
    "repackage", "mixtape", "digital_single", "feature",
    "skz_record", "skz_player",
]

Market = Literal["KR", "JP", "US", "GLOBAL"]


@router.get("/", response_model=Page[ReleaseResponse])
def list_releases(
    release_type: list[ReleaseType] | None = Query(None),
    market: list[Market] | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Release)
    if release_type:
        q = q.filter(Release.release_type.in_(release_type))
    if market:
        q = q.filter(Release.market.in_(market))
    total = q.count()
    items = q.order_by(Release.release_date.desc()).offset(skip).limit(limit).all()
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
    if tracks is None:
        release = db.query(Release).filter(Release.id == release_id).first()
        if not release:
            raise HTTPException(status_code=404, detail="Release not found")
        return release

    # Eager-load tracks + song (+ credits for full)
    track_load = joinedload(Release.tracks)
    if tracks == "full":
        from app.models.songs import Song
        from app.models.credits import SongCredit
        track_load = track_load.joinedload("song").subqueryload("credits")
    else:
        track_load = track_load.joinedload("song")

    release = (
        db.query(Release)
        .options(track_load)
        .filter(Release.id == release_id)
        .first()
    )
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


@router.get("/{release_id}/tracks", response_model=list[TrackResponse])
def get_release_tracks(release_id: int, db: Session = Depends(get_db)):
    release = (
        db.query(Release)
        .options(joinedload(Release.tracks).joinedload("song").subqueryload("credits"))
        .filter(Release.id == release_id)
        .first()
    )
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return sorted(release.tracks, key=lambda t: (t.disc_number or 1, t.track_number or 0))
