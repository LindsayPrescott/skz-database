from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class Collaborator(Base):
    __tablename__ = "collaborators"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False, unique=True)
    notes = Column(Text)

    credits = relationship("SongCredit", back_populates="collaborator")
