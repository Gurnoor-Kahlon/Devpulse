"""Add bounded publication recovery and scheduled observation freshness.

Revision ID: c82e7a1d904b
Revises: b31d8e0c6a10
"""

import sqlalchemy as sa
from alembic import op

revision = "c82e7a1d904b"
down_revision = "b31d8e0c6a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "check_runs",
        sa.Column(
            "next_publish_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_check_runs_publication",
        "check_runs",
        ["next_publish_at"],
        postgresql_where=sa.text("state IN ('pending', 'running')"),
    )
    op.add_column("monitors", sa.Column("last_scheduled_check_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("monitors", "last_scheduled_check_at")
    op.drop_index("ix_check_runs_publication", table_name="check_runs")
    op.drop_column("check_runs", "next_publish_at")
