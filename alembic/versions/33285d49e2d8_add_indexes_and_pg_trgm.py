"""add_indexes_and_pg_trgm

Revision ID: 33285d49e2d8
Revises: 7157369663ce
Create Date: 2026-04-05 05:00:30.368758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33285d49e2d8'
down_revision: Union[str, Sequence[str], None] = '7157369663ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable trigram extension for fast ILIKE search on title columns
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- song_credits ---
    op.create_index("ix_song_credits_song_id", "song_credits", ["song_id"])
    op.create_index("ix_song_credits_artist_id", "song_credits", ["artist_id"])
    op.create_index("ix_song_credits_collaborator_id", "song_credits", ["collaborator_id"])

    # --- tracks ---
    op.create_index("ix_tracks_release_id", "tracks", ["release_id"])
    op.create_index("ix_tracks_song_id", "tracks", ["song_id"])

    # --- releases ---
    op.create_index("ix_releases_artist_id", "releases", ["artist_id"])
    op.create_index("ix_releases_release_date", "releases", ["release_date"])
    op.create_index("ix_releases_release_type", "releases", ["release_type"])

    # --- songs (filter columns) ---
    op.create_index("ix_songs_parent_song_id", "songs", ["parent_song_id"])
    op.create_index("ix_songs_release_status", "songs", ["release_status"])
    op.create_index("ix_songs_language", "songs", ["language"])

    # --- songs (pg_trgm GIN indexes for search()) ---
    op.create_index("ix_songs_title_trgm", "songs", ["title"], postgresql_using="gin",
                    postgresql_ops={"title": "gin_trgm_ops"})
    op.create_index("ix_songs_title_korean_trgm", "songs", ["title_korean"], postgresql_using="gin",
                    postgresql_ops={"title_korean": "gin_trgm_ops"})
    op.create_index("ix_songs_title_romanized_trgm", "songs", ["title_romanized"], postgresql_using="gin",
                    postgresql_ops={"title_romanized": "gin_trgm_ops"})
    op.create_index("ix_songs_title_japanese_trgm", "songs", ["title_japanese"], postgresql_using="gin",
                    postgresql_ops={"title_japanese": "gin_trgm_ops"})


def downgrade() -> None:
    op.drop_index("ix_songs_title_japanese_trgm", "songs")
    op.drop_index("ix_songs_title_romanized_trgm", "songs")
    op.drop_index("ix_songs_title_korean_trgm", "songs")
    op.drop_index("ix_songs_title_trgm", "songs")

    op.drop_index("ix_songs_language", "songs")
    op.drop_index("ix_songs_release_status", "songs")
    op.drop_index("ix_songs_parent_song_id", "songs")

    op.drop_index("ix_releases_release_type", "releases")
    op.drop_index("ix_releases_release_date", "releases")
    op.drop_index("ix_releases_artist_id", "releases")

    op.drop_index("ix_tracks_song_id", "tracks")
    op.drop_index("ix_tracks_release_id", "tracks")

    op.drop_index("ix_song_credits_collaborator_id", "song_credits")
    op.drop_index("ix_song_credits_artist_id", "song_credits")
    op.drop_index("ix_song_credits_song_id", "song_credits")

    # Note: does not drop pg_trgm extension — it may be used by other tables
