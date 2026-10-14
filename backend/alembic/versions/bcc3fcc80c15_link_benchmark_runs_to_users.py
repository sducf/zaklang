"""link benchmark runs to users

Revision ID: bcc3fcc80c15
Revises: 769b8a4fe047
Create Date: 2026-10-13 21:28:50.005851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bcc3fcc80c15'
down_revision: Union[str, Sequence[str], None] = '769b8a4fe047'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.Uuid(),
                nullable=False,
            )
        )

        batch_op.create_foreign_key(
            "fk_benchmark_runs_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("benchmark_runs") as batch_op:
        batch_op.drop_constraint(
            "fk_benchmark_runs_user_id_users",
            type_="foreignkey",
        )

        batch_op.drop_column("user_id")