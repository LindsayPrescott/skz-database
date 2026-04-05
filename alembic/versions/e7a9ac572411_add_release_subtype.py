"""add_release_subtype

Revision ID: e7a9ac572411
Revises: 33285d49e2d8
Create Date: 2026-04-05 05:19:52.200470

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a9ac572411'
down_revision: Union[str, Sequence[str], None] = '33285d49e2d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("releases", sa.Column("release_subtype", sa.String(30), nullable=True))

    # Migrate existing SKZ-specific release types into the new column
    op.execute("""
        UPDATE releases
        SET release_type = 'digital_single', release_subtype = 'skz_record'
        WHERE release_type = 'skz_record'
    """)
    op.execute("""
        UPDATE releases
        SET release_type = 'digital_single', release_subtype = 'skz_player'
        WHERE release_type = 'skz_player'
    """)


def downgrade() -> None:
    # Restore original release_type values from release_subtype
    op.execute("""
        UPDATE releases
        SET release_type = release_subtype
        WHERE release_subtype IN ('skz_record', 'skz_player')
    """)
    op.drop_column("releases", "release_subtype")
