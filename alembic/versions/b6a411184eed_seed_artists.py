"""seed artists

Revision ID: b6a411184eed
Revises: 4ee870d8ee1e
Create Date: 2026-04-02 15:10:31.366042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6a411184eed'
down_revision: Union[str, Sequence[str], None] = '4ee870d8ee1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    artists = sa.table(
        "artists",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("name_korean", sa.String),
        sa.column("name_romanized", sa.String),
        sa.column("artist_type", sa.String),
        sa.column("birth_name", sa.String),
        sa.column("birth_name_korean", sa.String),
        sa.column("birth_date", sa.Date),
        sa.column("nationality", sa.String),
        sa.column("is_former_member", sa.Boolean),
    )

    artist_members = sa.table(
        "artist_members",
        sa.column("parent_artist_id", sa.Integer),
        sa.column("child_artist_id", sa.Integer),
    )

    # ------------------------------------------------------------------
    # Artists: IDs are fixed so artist_members inserts can reference them
    # Group: 1
    # Units: 2 (3RACHA), 3 (DanceRacha), 4 (VocalRacha)
    # Members: 5–13
    # ------------------------------------------------------------------
    op.bulk_insert(artists, [
        # Group
        {
            "id": 1,
            "name": "Stray Kids",
            "name_korean": "스트레이 키즈",
            "name_romanized": "Stray Kids",
            "artist_type": "group",
            "birth_name": None,
            "birth_name_korean": None,
            "birth_date": None,
            "nationality": None,
            "is_former_member": False,
        },
        # Units
        {
            "id": 2,
            "name": "3RACHA",
            "name_korean": "쓰리라차",
            "name_romanized": "3RACHA",
            "artist_type": "unit",
            "birth_name": None,
            "birth_name_korean": None,
            "birth_date": None,
            "nationality": None,
            "is_former_member": False,
        },
        {
            "id": 3,
            "name": "DanceRacha",
            "name_korean": "댄스라차",
            "name_romanized": "DanceRacha",
            "artist_type": "unit",
            "birth_name": None,
            "birth_name_korean": None,
            "birth_date": None,
            "nationality": None,
            "is_former_member": False,
        },
        {
            "id": 4,
            "name": "VocalRacha",
            "name_korean": "보컬라차",
            "name_romanized": "VocalRacha",
            "artist_type": "unit",
            "birth_name": None,
            "birth_name_korean": None,
            "birth_date": None,
            "nationality": None,
            "is_former_member": False,
        },
        # Members
        {
            "id": 5,
            "name": "Bang Chan",
            "name_korean": "방찬",
            "name_romanized": "Bang Chan",
            "artist_type": "member",
            "birth_name": "Christopher Bang",
            "birth_name_korean": "방찬",
            "birth_date": "2000-10-03",
            "nationality": "Australian",
            "is_former_member": False,
        },
        {
            "id": 6,
            "name": "Lee Know",
            "name_korean": "리노",
            "name_romanized": "Lee Know",
            "artist_type": "member",
            "birth_name": "Lee Minho",
            "birth_name_korean": "이민호",
            "birth_date": "2000-10-25",
            "nationality": "Korean",
            "is_former_member": False,
        },
        {
            "id": 7,
            "name": "Changbin",
            "name_korean": "창빈",
            "name_romanized": "Changbin",
            "artist_type": "member",
            "birth_name": "Seo Changbin",
            "birth_name_korean": "서창빈",
            "birth_date": "2000-08-11",
            "nationality": "Korean",
            "is_former_member": False,
        },
        {
            "id": 8,
            "name": "Hyunjin",
            "name_korean": "현진",
            "name_romanized": "Hyunjin",
            "artist_type": "member",
            "birth_name": "Hwang Hyunjin",
            "birth_name_korean": "황현진",
            "birth_date": "2000-03-20",
            "nationality": "Korean",
            "is_former_member": False,
        },
        {
            "id": 9,
            "name": "Han",
            "name_korean": "한",
            "name_romanized": "Han",
            "artist_type": "member",
            "birth_name": "Han Jisung",
            "birth_name_korean": "한지성",
            "birth_date": "2000-09-14",
            "nationality": "Korean",
            "is_former_member": False,
        },
        {
            "id": 10,
            "name": "Felix",
            "name_korean": "필릭스",
            "name_romanized": "Felix",
            "artist_type": "member",
            "birth_name": "Lee Yongbok",
            "birth_name_korean": "이용복",
            "birth_date": "2000-09-15",
            "nationality": "Australian",
            "is_former_member": False,
        },
        {
            "id": 11,
            "name": "Seungmin",
            "name_korean": "승민",
            "name_romanized": "Seungmin",
            "artist_type": "member",
            "birth_name": "Kim Seungmin",
            "birth_name_korean": "김승민",
            "birth_date": "2000-09-22",
            "nationality": "Korean",
            "is_former_member": False,
        },
        {
            "id": 12,
            "name": "I.N",
            "name_korean": "아이엔",
            "name_romanized": "I.N",
            "artist_type": "member",
            "birth_name": "Yang Jeongin",
            "birth_name_korean": "양정인",
            "birth_date": "2001-02-08",
            "nationality": "Korean",
            "is_former_member": False,
        },
        {
            "id": 13,
            "name": "Woojin",
            "name_korean": "우진",
            "name_romanized": "Woojin",
            "artist_type": "member",
            "birth_name": "Kim Woojin",
            "birth_name_korean": "김우진",
            "birth_date": "1997-11-26",
            "nationality": "Korean",
            "is_former_member": True,
        },
    ])

    # ------------------------------------------------------------------
    # Unit / group memberships
    # ------------------------------------------------------------------
    op.bulk_insert(artist_members, [
        # Stray Kids members
        {"parent_artist_id": 1, "child_artist_id": 5},   # Bang Chan
        {"parent_artist_id": 1, "child_artist_id": 6},   # Lee Know
        {"parent_artist_id": 1, "child_artist_id": 7},   # Changbin
        {"parent_artist_id": 1, "child_artist_id": 8},   # Hyunjin
        {"parent_artist_id": 1, "child_artist_id": 9},   # Han
        {"parent_artist_id": 1, "child_artist_id": 10},  # Felix
        {"parent_artist_id": 1, "child_artist_id": 11},  # Seungmin
        {"parent_artist_id": 1, "child_artist_id": 12},  # I.N
        {"parent_artist_id": 1, "child_artist_id": 13},  # Woojin (former)
        # 3RACHA: Bang Chan, Changbin, Han
        {"parent_artist_id": 2, "child_artist_id": 5},
        {"parent_artist_id": 2, "child_artist_id": 7},
        {"parent_artist_id": 2, "child_artist_id": 9},
        # DanceRacha: Lee Know, Hyunjin, Felix
        {"parent_artist_id": 3, "child_artist_id": 6},
        {"parent_artist_id": 3, "child_artist_id": 8},
        {"parent_artist_id": 3, "child_artist_id": 10},
        # VocalRacha: Seungmin, I.N (Woojin was original vocal unit member)
        {"parent_artist_id": 4, "child_artist_id": 11},
        {"parent_artist_id": 4, "child_artist_id": 12},
        {"parent_artist_id": 4, "child_artist_id": 13},  # Woojin (former vocal unit)
    ])


def downgrade() -> None:
    op.execute("DELETE FROM artist_members WHERE parent_artist_id IN (1,2,3,4)")
    op.execute("DELETE FROM artists WHERE id BETWEEN 1 AND 13")
