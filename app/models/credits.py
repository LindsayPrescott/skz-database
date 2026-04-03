from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class SongCredit(Base):
    __tablename__ = "song_credits"

    id = Column(Integer, primary_key=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    # NULL when credit_name_raw is used (external collaborators)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=True)
    # Raw name string for collaborators not in the artists table
    credit_name_raw = Column(String(300))
    # vocalist | rapper | featured | lyricist | composer | arranger | producer | executive_producer
    role = Column(String(30), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)

    __table_args__ = (
        UniqueConstraint("song_id", "artist_id", "credit_name_raw", "role", name="uq_song_credit"),
    )

    song = relationship("Song", back_populates="credits")
    artist = relationship("Artist", back_populates="credits")
