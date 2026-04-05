from sqlalchemy import Boolean, Column, Date, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class Release(Base):
    __tablename__ = "releases"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    title_korean = Column(String(500))
    title_romanized = Column(String(500))
    # studio_album | compilation_album | repackage | ep | single_album |
    # digital_single | mixtape | ost | feature | predebut
    release_type = Column(String(30), nullable=False)
    # Group-specific sub-classification (e.g. 'skz_record', 'skz_player')
    release_subtype = Column(String(30), nullable=True)
    release_date = Column(Date)
    # 'year' | 'month' | 'day' — how precise the release_date is
    release_date_precision = Column(String(10), default="day")
    label = Column(String(200))
    # 'KR' | 'JP' | 'US' | 'GLOBAL' | 'OTHER'
    market = Column(String(10), default="KR")
    catalog_number = Column(String(100))
    formats = Column(String(200))  # e.g. "CD, Digital"
    artist_id = Column(Integer, ForeignKey("artists.id"))
    wikipedia_url = Column(String(500))
    fandom_url = Column(String(500))
    cover_image_url = Column(String(500))
    is_verified = Column(Boolean, nullable=False, default=False)
    # 'wikipedia' | 'fandom' | 'spotify' | 'manual'
    source = Column(String(20), default="manual")
    notes = Column(Text)

    artist = relationship("Artist", back_populates="releases")
    tracks = relationship("Track", back_populates="release", cascade="all, delete-orphan")
    chart_entries = relationship("ChartEntry", back_populates="release")
    sales = relationship("ReleaseSales", back_populates="release", cascade="all, delete-orphan")
