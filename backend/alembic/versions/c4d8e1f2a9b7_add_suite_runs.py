"""add suite runs

Revision ID: c4d8e1f2a9b7
Revises: a7c9e2d4f1b6
Create Date: 2026-11-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d8e1f2a9b7"
down_revision: Union[str, Sequence[str], None] = "a7c9e2d4f1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "suite_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cli_suite_run_id", sa.String(length=100), nullable=False),
        sa.Column("suite", sa.String(length=20), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("spec_version", sa.String(length=50), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_suite_runs_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cli_suite_run_id"),
    )
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.add_column(sa.Column("suite_run_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_benchmark_runs_suite_run_id", ["suite_run_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_benchmark_runs_suite_run_id_suite_runs", "suite_runs", ["suite_run_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.drop_constraint("fk_benchmark_runs_suite_run_id_suite_runs", type_="foreignkey")
        batch_op.drop_index("ix_benchmark_runs_suite_run_id")
        batch_op.drop_column("suite_run_id")
    op.drop_table("suite_runs")
