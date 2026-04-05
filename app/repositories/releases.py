from __future__ import annotations

from sqlalchemy import extract, nulls_last
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track


class ReleaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        release_type: list[str] | None,
        market: list[str] | None,
        artist_id: int | None,
        year_from: int | None,
        year_to: int | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Release]]:
        q = self.db.query(Release)
        if release_type:
            q = q.filter(Release.release_type.in_(release_type))
        if market:
            q = q.filter(Release.market.in_(market))
        if artist_id is not None:
            q = q.filter(Release.artist_id == artist_id)
        if year_from:
            q = q.filter(extract("year", Release.release_date) >= year_from)
        if year_to:
            q = q.filter(extract("year", Release.release_date) <= year_to)
        total = q.count()
        items = q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit).all()
        return total, items

    def get(self, release_id: int) -> Release | None:
        return self.db.query(Release).filter(Release.id == release_id).first()

    def get_with_tracks(self, release_id: int, full: bool) -> Release | None:
        if full:
            track_load = (
                joinedload(Release.tracks)
                .joinedload(Track.song)
                .subqueryload(Song.credits)
                .joinedload(SongCredit.artist)
            )
            track_load_collab = (
                joinedload(Release.tracks)
                .joinedload(Track.song)
                .subqueryload(Song.credits)
                .joinedload(SongCredit.collaborator)
            )
            options = [track_load, track_load_collab]
        else:
            options = [joinedload(Release.tracks).joinedload(Track.song)]

        return (
            self.db.query(Release)
            .options(*options)
            .filter(Release.id == release_id)
            .first()
        )
