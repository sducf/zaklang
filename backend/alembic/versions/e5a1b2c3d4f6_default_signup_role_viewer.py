"""default new users to the viewer role

Revision ID: e5a1b2c3d4f6
Revises: d24b8c6f1a03
Create Date: 2026-11-24 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a1b2c3d4f6"
down_revision: Union[str, Sequence[str], None] = "d24b8c6f1a03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Existing users keep their current role."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default="viewer",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default=None,
        )
