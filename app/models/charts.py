from sqlalchemy import Column, Date, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class ChartEntry(Base):
    __tablename__ = "chart_entries"

    id = Column(Integer, primary_key=True)
    # 'release' | 'song'
    entity_type = Column(String(10), nullable=False)
    release_id = Column(Integer, ForeignKey("releases.id"), nullable=True)
    song_id = Column(Integer, ForeignKey("songs.id"), nullable=True)
    chart_name = Column(String(200), nullable=False)  # e.g. "Billboard Hot 100"
    chart_region = Column(String(10))                 # e.g. "US", "KR"
    peak_position = Column(Integer)
    chart_date = Column(Date)
    certifications = Column(String(500))              # e.g. "RIAA Platinum"
    notes = Column(Text)

    release = relationship("Release", back_populates="chart_entries")
    song = relationship("Song", back_populates="chart_entries")


class ReleaseSales(Base):
    __tablename__ = "release_sales"

    id = Column(Integer, primary_key=True)
    release_id = Column(Integer, ForeignKey("releases.id"), nullable=False)
    region = Column(String(10), nullable=False)       # 'KR', 'JP', 'US', 'WW'
    quantity = Column(Integer)
    # 'physical' | 'digital' | 'streaming' | 'combined'
    sale_type = Column(String(20), default="physical")
    as_of_date = Column(Date)
    notes = Column(Text)

    release = relationship("Release", back_populates="sales")
