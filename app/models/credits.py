from sqlalchemy import Boolean, CheckConstraint, Column, Index, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class SongCredit(Base):
    __tablename__ = "song_credits"

    id = Column(Integer, primary_key=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    # Set for Stray Kids members and units
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=True)
    # Set for external collaborators (Versachoi, HotSauce, etc.)
    collaborator_id = Column(Integer, ForeignKey("collaborators.id"), nullable=True)
    # vocalist | rapper | featured | lyricist | composer | arranger | producer | executive_producer
    role = Column(String(30), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)

    __table_args__ = (
        UniqueConstraint("song_id", "artist_id", "collaborator_id", "role", name="uq_song_credit"),
        CheckConstraint("artist_id IS NOT NULL OR collaborator_id IS NOT NULL", name="ck_song_credit_has_entity"),
        Index("ix_song_credits_song_id", "song_id"),
        Index("ix_song_credits_artist_id", "artist_id"),
        Index("ix_song_credits_collaborator_id", "collaborator_id"),
    )

    song = relationship("Song", back_populates="credits")
    artist = relationship("Artist", back_populates="credits")
    collaborator = relationship("Collaborator", back_populates="credits")
