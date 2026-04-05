# Import all models so Alembic's autogenerate can find them via Base.metadata.
# If a model file is never imported, its table will be invisible to Alembic.

from app.models.base import Base
from app.models.artists import Artist, ArtistMember
from app.models.releases import Release
from app.models.songs import Song, Track
from app.models.collaborators import Collaborator
from app.models.credits import SongCredit
from app.models.charts import ChartEntry, ReleaseSales

__all__ = [
    "Base",
    "Artist",
    "ArtistMember",
    "Release",
    "Song",
    "Track",
    "Collaborator",
    "SongCredit",
    "ChartEntry",
    "ReleaseSales",
]
