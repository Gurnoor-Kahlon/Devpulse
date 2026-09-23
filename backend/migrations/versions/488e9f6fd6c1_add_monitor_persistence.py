"""add monitor persistence

Revision ID: 488e9f6fd6c1
Revises: a4c16df5c2ab
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "488e9f6fd6c1"
down_revision: str | Sequence[str] | None = "a4c16df5c2ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("method", sa.String(length=4), nullable=False),
        sa.Column("expected_status", sa.Integer(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_state", sa.String(length=20), nullable=False),
        sa.Column("last_completed_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "current_state IN ('unknown', 'operational', 'down', 'confirming_failure')",
            name=op.f("ck_monitors_current_state"),
        ),
        sa.CheckConstraint("method IN ('GET', 'HEAD')", name=op.f("ck_monitors_method")),
        sa.CheckConstraint("url ~ '^https?://'", name=op.f("ck_monitors_url_scheme")),
        sa.CheckConstraint(
            "(enabled AND next_due_at IS NOT NULL) OR (NOT enabled AND next_due_at IS NULL)",
            name=op.f("ck_monitors_due_when_enabled"),
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) BETWEEN 1 AND 100", name=op.f("ck_monitors_name_length")
        ),
        sa.CheckConstraint(
            "char_length(url) BETWEEN 1 AND 2048", name=op.f("ck_monitors_url_length")
        ),
        sa.CheckConstraint(
            "configuration_version > 0", name=op.f("ck_monitors_configuration_version")
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR NOT enabled", name=op.f("ck_monitors_archived_disabled")
        ),
        sa.CheckConstraint(
            "expected_status BETWEEN 200 AND 599", name=op.f("ck_monitors_expected_status")
        ),
        sa.CheckConstraint(
            "interval_seconds BETWEEN 60 AND 86400", name=op.f("ck_monitors_interval_seconds")
        ),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 10", name=op.f("ck_monitors_timeout_seconds")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_monitors_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitors")),
    )
    op.create_index(
        "ix_monitors_next_due_at",
        "monitors",
        ["next_due_at"],
        unique=False,
        postgresql_where=sa.text("enabled AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_monitors_user_id_created_at_id",
        "monitors",
        ["user_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_monitors_user_id_created_at_id", table_name="monitors")
    op.drop_index(
        "ix_monitors_next_due_at",
        table_name="monitors",
        postgresql_where=sa.text("enabled AND deleted_at IS NULL"),
    )
    op.drop_table("monitors")
