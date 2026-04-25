"""add_musicbrainz_id_to_songs

Revision ID: e9269245b1b1
Revises: a6d0a556c97d
Create Date: 2026-04-16 09:31:44.353897

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9269245b1b1'
down_revision: Union[str, Sequence[str], None] = 'a6d0a556c97d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('songs', sa.Column('musicbrainz_id', sa.String(length=36), nullable=True))
    op.create_unique_constraint('uq_songs_musicbrainz_id', 'songs', ['musicbrainz_id'])


def downgrade() -> None:
    op.drop_constraint('uq_songs_musicbrainz_id', 'songs', type_='unique')
    op.drop_column('songs', 'musicbrainz_id')
