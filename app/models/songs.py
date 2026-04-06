from sqlalchemy import Boolean, Column, Index, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    # Self-referential: version songs point to their canonical parent
    parent_song_id = Column(Integer, ForeignKey("songs.id"), nullable=True)
    # e.g. "Korean", "English", "Hip", "Festival", "Inst."
    version_label = Column(String(100), nullable=True)
    title_korean = Column(String(500))
    title_romanized = Column(String(500))
    title_japanese = Column(String(500))
    duration_seconds = Column(Integer)
    # ISO 639-1: 'ko' | 'en' | 'ja' | 'multi' | 'unknown'
    language = Column(String(10), default="ko")
    has_korean_ver = Column(Boolean, nullable=False, default=False)
    has_english_ver = Column(Boolean, nullable=False, default=False)
    has_japanese_ver = Column(Boolean, nullable=False, default=False)
    # released | unreleased | snippet | stage_only | predebut | cover
    release_status = Column(String(20), nullable=False, default="released")
    is_instrumental = Column(Boolean, nullable=False, default=False)
    original_artist = Column(String(300))  # For covers
    spotify_id = Column(String(100), unique=True)
    isrc = Column(String(20), unique=True)
    wikipedia_url = Column(String(500))
    fandom_url = Column(String(500))
    youtube_url = Column(String(500))
    is_verified = Column(Boolean, nullable=False, default=False)
    # 'wikipedia' | 'fandom' | 'spotify' | 'manual'
    source = Column(String(20), default="manual")
    notes = Column(Text)

    __table_args__ = (
        Index("ix_songs_parent_song_id", "parent_song_id"),
        Index("ix_songs_release_status", "release_status"),
        Index("ix_songs_language", "language"),
        Index("ix_songs_title_trgm", "title", postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
        Index("ix_songs_title_korean_trgm", "title_korean", postgresql_using="gin", postgresql_ops={"title_korean": "gin_trgm_ops"}),
        Index("ix_songs_title_romanized_trgm", "title_romanized", postgresql_using="gin", postgresql_ops={"title_romanized": "gin_trgm_ops"}),
        Index("ix_songs_title_japanese_trgm", "title_japanese", postgresql_using="gin", postgresql_ops={"title_japanese": "gin_trgm_ops"}),
    )

    versions = relationship("Song", foreign_keys="[Song.parent_song_id]", back_populates="parent")
    parent = relationship("Song", foreign_keys="[Song.parent_song_id]", remote_side="[Song.id]", back_populates="versions")
    tracks = relationship("Track", back_populates="song")
    credits = relationship("SongCredit", back_populates="song", cascade="all, delete-orphan", order_by="SongCredit.role")
    chart_entries = relationship("ChartEntry", back_populates="song")


class Track(Base):
    """An appearance of a Song on a Release (one song can appear on many releases)."""
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)
    release_id = Column(Integer, ForeignKey("releases.id"), nullable=False)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=False)
    track_number = Column(Integer)
    disc_number = Column(Integer, default=1)
    is_title_track = Column(Boolean, nullable=False, default=False)
    is_intro = Column(Boolean, nullable=False, default=False)
    is_outro = Column(Boolean, nullable=False, default=False)
    is_bonus = Column(Boolean, nullable=False, default=False)
    version_note = Column(String(200))  # e.g. "Japanese ver.", "Inst."

    __table_args__ = (
        Index("ix_tracks_release_id", "release_id"),
        Index("ix_tracks_song_id", "song_id"),
    )

    release = relationship("Release", back_populates="tracks")
    song = relationship("Song", back_populates="tracks")
