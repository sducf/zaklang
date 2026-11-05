"""add pair id to benchmark runs

Revision ID: 91d2e7f4a6b8
Revises: 4f7c5e1a2b3c
Create Date: 2026-11-05 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91d2e7f4a6b8"
down_revision: Union[str, Sequence[str], None] = "4f7c5e1a2b3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.add_column(
            sa.Column("pair_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_index(
            "ix_benchmark_runs_pair_id",
            ["pair_id"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.drop_index("ix_benchmark_runs_pair_id")
        batch_op.drop_column("pair_id")
