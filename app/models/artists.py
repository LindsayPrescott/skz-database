from sqlalchemy import Boolean, Column, Date, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    name_korean = Column(String(200))
    name_romanized = Column(String(200))
    # 'group' | 'unit' | 'member'
    artist_type = Column(String(20), nullable=False)
    birth_name = Column(String(200))
    birth_name_korean = Column(String(200))
    birth_date = Column(Date)
    nationality = Column(String(100))
    is_former_member = Column(Boolean, nullable=False, default=False)
    spotify_id = Column(String(100), unique=True)
    notes = Column(Text)

    # Members of this unit/group (parent → children)
    memberships = relationship(
        "ArtistMember",
        foreign_keys="ArtistMember.parent_artist_id",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    # Units/groups this artist belongs to (child → parents)
    member_of = relationship(
        "ArtistMember",
        foreign_keys="ArtistMember.child_artist_id",
        back_populates="child",
    )

    releases = relationship("Release", back_populates="artist")
    credits = relationship("SongCredit", back_populates="artist")


class ArtistMember(Base):
    """Self-referential join: maps members to their unit/group."""
    __tablename__ = "artist_members"

    parent_artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)
    child_artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)

    parent = relationship("Artist", foreign_keys=[parent_artist_id], back_populates="memberships")
    child = relationship("Artist", foreign_keys=[child_artist_id], back_populates="member_of")
