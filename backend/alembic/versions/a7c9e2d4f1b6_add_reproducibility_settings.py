"""add reproducibility settings to benchmark runs

Revision ID: a7c9e2d4f1b6
Revises: 91d2e7f4a6b8
Create Date: 2026-11-05 05:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c9e2d4f1b6"
down_revision: Union[str, Sequence[str], None] = "91d2e7f4a6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.add_column(
            sa.Column("seed", sa.Integer(), nullable=False, server_default="0"),
        )
        batch_op.add_column(
            sa.Column("spec_version", sa.String(length=50), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "prompt_version",
                sa.String(length=50),
                nullable=False,
                server_default="1",
            ),
        )
        batch_op.add_column(
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=False,
                server_default="3",
            ),
        )
        batch_op.alter_column("seed", server_default=None)
        batch_op.alter_column("prompt_version", server_default=None)
        batch_op.alter_column("max_attempts", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.drop_column("max_attempts")
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("spec_version")
        batch_op.drop_column("seed")
