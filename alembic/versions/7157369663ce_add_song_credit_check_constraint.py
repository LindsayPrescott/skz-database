"""add_song_credit_check_constraint

Revision ID: 7157369663ce
Revises: 74519399055f
Create Date: 2026-04-05 04:38:35.437551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7157369663ce'
down_revision: Union[str, Sequence[str], None] = '74519399055f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_song_credit_has_entity",
        "song_credits",
        "artist_id IS NOT NULL OR collaborator_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_song_credit_has_entity", "song_credits", type_="check")
