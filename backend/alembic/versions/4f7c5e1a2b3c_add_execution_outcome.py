"""add execution outcome to evaluations

Revision ID: 4f7c5e1a2b3c
Revises: bcc3fcc80c15
Create Date: 2026-10-26 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f7c5e1a2b3c"
down_revision: Union[str, Sequence[str], None] = "bcc3fcc80c15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluations",
        sa.Column("exec_outcome", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluations", "exec_outcome")
