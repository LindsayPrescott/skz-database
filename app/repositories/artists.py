from __future__ import annotations

from sqlalchemy import func, nulls_last, or_
from sqlalchemy.orm import Session, joinedload

from app.models.artists import Artist, ArtistMember
from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.releases import Release
from app.models.songs import Song, Track


class ArtistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self, artist_type: list[str] | None, skip: int, limit: int
    ) -> tuple[int, list[Artist]]:
        q = self.db.query(Artist)
        if artist_type:
            q = q.filter(Artist.artist_type.in_(artist_type))
        total = q.count()
        items = q.order_by(Artist.id).offset(skip).limit(limit).all()
        return total, items

    def get_with_memberships(self, artist_id: int) -> Artist | None:
        return (
            self.db.query(Artist)
            .options(
                joinedload(Artist.memberships).joinedload(ArtistMember.child),
                joinedload(Artist.member_of).joinedload(ArtistMember.parent),
            )
            .filter(Artist.id == artist_id)
            .first()
        )

    def get(self, artist_id: int) -> Artist | None:
        return self.db.query(Artist).filter(Artist.id == artist_id).first()

    def list_releases(
        self,
        artist_id: int,
        release_type: list[str] | None,
        role: list[str] | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Release]]:
        credited_release_ids = (
            self.db.query(Track.release_id)
            .join(SongCredit, SongCredit.song_id == Track.song_id)
            .filter(SongCredit.artist_id == artist_id)
        )
        if role:
            credited_release_ids = credited_release_ids.filter(SongCredit.role.in_(role))
            q = self.db.query(Release).filter(Release.id.in_(credited_release_ids)).distinct()
        else:
            q = (
                self.db.query(Release)
                .filter(
                    or_(
                        Release.artist_id == artist_id,
                        Release.id.in_(credited_release_ids),
                    )
                )
                .distinct()
            )
        if release_type:
            q = q.filter(Release.release_type.in_(release_type))
        total = q.count()
        items = q.order_by(nulls_last(Release.release_date.desc())).offset(skip).limit(limit).all()
        return total, items

    def list_credits(
        self,
        artist_id: int,
        role: list[str] | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[tuple[Song, str]]]:
        q = (
            self.db.query(Song, SongCredit.role)
            .join(SongCredit, SongCredit.song_id == Song.id)
            .filter(SongCredit.artist_id == artist_id)
        )
        if role:
            q = q.filter(SongCredit.role.in_(role))
        total = q.count()
        rows = q.order_by(Song.title).offset(skip).limit(limit).all()
        return total, rows

    def get_collaborators(
        self, artist_id: int
    ) -> tuple[list, list]:
        artist_song_ids = (
            self.db.query(SongCredit.song_id)
            .filter(SongCredit.artist_id == artist_id)
            .distinct()
            .subquery()
        )
        co_artists = (
            self.db.query(Artist.id, Artist.name, func.count(SongCredit.id).label("count"))
            .join(SongCredit, SongCredit.artist_id == Artist.id)
            .filter(SongCredit.song_id.in_(artist_song_ids), Artist.id != artist_id)
            .group_by(Artist.id, Artist.name)
            .all()
        )
        co_collaborators = (
            self.db.query(Collaborator.id, Collaborator.name, func.count(SongCredit.id).label("count"))
            .join(SongCredit, SongCredit.collaborator_id == Collaborator.id)
            .filter(SongCredit.song_id.in_(artist_song_ids))
            .group_by(Collaborator.id, Collaborator.name)
            .all()
        )
        return co_artists, co_collaborators
