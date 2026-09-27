"""Add response assertions

Revision ID: e15a9c7d204f
Revises: d93f8b2e015c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e15a9c7d204f"
down_revision: str | Sequence[str] | None = "d93f8b2e015c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assertions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("monitor_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("pointer", sa.String(length=512), nullable=False),
        sa.Column("expected", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(expected) IN ('string', 'number', 'boolean', 'null')",
            name=op.f("ck_assertions_scalar"),
        ),
        sa.CheckConstraint(
            "kind IN ('text_contains', 'json_equals')", name=op.f("ck_assertions_kind")
        ),
        sa.CheckConstraint(
            "char_length(pointer) <= 512", name=op.f("ck_assertions_pointer_length")
        ),
        sa.CheckConstraint("position BETWEEN 0 AND 9", name=op.f("ck_assertions_position")),
        sa.ForeignKeyConstraint(
            ["monitor_id"],
            ["monitors.id"],
            name=op.f("fk_assertions_monitor_id_monitors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assertions")),
        sa.UniqueConstraint(
            "monitor_id", "position", name=op.f("uq_assertions_monitor_id_position")
        ),
    )
    op.add_column(
        "checks",
        sa.Column(
            "assertion_results",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("checks", "assertion_results")
    op.drop_table("assertions")
