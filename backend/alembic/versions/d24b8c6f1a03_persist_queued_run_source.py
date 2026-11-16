"""persist source for queued benchmark runs

Revision ID: d24b8c6f1a03
Revises: c4d8e1f2a9b7
Create Date: 2026-11-16 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d24b8c6f1a03"
down_revision: Union[str, Sequence[str], None] = "c4d8e1f2a9b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "benchmark_runs",
        sa.Column("source", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("benchmark_runs", "source")
