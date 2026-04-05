"""add_check_constraints_for_enums

Revision ID: ced17bba4ac8
Revises: e7a9ac572411
Create Date: 2026-04-05 05:24:29.003325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ced17bba4ac8'
down_revision: Union[str, Sequence[str], None] = 'e7a9ac572411'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # releases
    op.create_check_constraint(
        "ck_releases_release_type",
        "releases",
        "release_type IN ('studio_album','ep','single_album','compilation_album',"
        "'repackage','mixtape','digital_single','feature')",
    )
    op.create_check_constraint(
        "ck_releases_market",
        "releases",
        "market IN ('KR','JP','US','GLOBAL')",
    )
    op.create_check_constraint(
        "ck_releases_release_date_precision",
        "releases",
        "release_date_precision IN ('day','month','year')",
    )
    op.create_check_constraint(
        "ck_releases_source",
        "releases",
        "source IS NULL OR source IN ('wikipedia','fandom','spotify','manual')",
    )

    # artists
    op.create_check_constraint(
        "ck_artists_artist_type",
        "artists",
        "artist_type IN ('group','unit','member')",
    )

    # song_credits
    op.create_check_constraint(
        "ck_song_credits_role",
        "song_credits",
        "role IN ('vocalist','rapper','featured','lyricist','composer',"
        "'arranger','producer','executive_producer')",
    )

    # songs
    op.create_check_constraint(
        "ck_songs_language",
        "songs",
        "language IS NULL OR language IN ('ko','en','ja','multi','unknown')",
    )
    op.create_check_constraint(
        "ck_songs_release_status",
        "songs",
        "release_status IN ('released','unreleased','snippet','stage_only','predebut','cover')",
    )
    op.create_check_constraint(
        "ck_songs_source",
        "songs",
        "source IS NULL OR source IN ('wikipedia','fandom','spotify','manual')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_songs_source", "songs", type_="check")
    op.drop_constraint("ck_songs_release_status", "songs", type_="check")
    op.drop_constraint("ck_songs_language", "songs", type_="check")
    op.drop_constraint("ck_song_credits_role", "song_credits", type_="check")
    op.drop_constraint("ck_artists_artist_type", "artists", type_="check")
    op.drop_constraint("ck_releases_source", "releases", type_="check")
    op.drop_constraint("ck_releases_release_date_precision", "releases", type_="check")
    op.drop_constraint("ck_releases_market", "releases", type_="check")
    op.drop_constraint("ck_releases_release_type", "releases", type_="check")
