"""Add notification deliveries and retention index

Revision ID: f16b4d8e302a
Revises: e15a9c7d204f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f16b4d8e302a"
down_revision: str | Sequence[str] | None = "e15a9c7d204f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("on_open", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("on_recovery", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "configuration_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.CheckConstraint(
            "configuration_version > 0", name=op.f("ck_notification_channels_version")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_channels_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_channels")),
        sa.UniqueConstraint("user_id", name=op.f("uq_notification_channels_user_id")),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("transition", sa.String(length=10), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "(status = 'pending' AND next_attempt_at IS NOT NULL AND lease_token IS NULL "
            "AND lease_expires_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'sending' AND next_attempt_at IS NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND completed_at IS NULL) OR "
            "(status IN ('sent', 'failed', 'cancelled') AND next_attempt_at IS NULL AND "
            "lease_token IS NULL AND lease_expires_at IS NULL AND completed_at IS NOT "
            "NULL)",
            name=op.f("ck_notification_deliveries_lifecycle"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')",
            name=op.f("ck_notification_deliveries_status"),
        ),
        sa.CheckConstraint(
            "transition IN ('opened', 'resolved')",
            name=op.f("ck_notification_deliveries_transition"),
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 5", name=op.f("ck_notification_deliveries_attempt_count")
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["notification_channels.id"],
            name=op.f("fk_notification_deliveries_channel_id_notification_channels"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_notification_deliveries_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_deliveries")),
        sa.UniqueConstraint(
            "incident_id",
            "transition",
            "channel_id",
            name=op.f("uq_notification_deliveries_incident_id_transition_channel_id"),
        ),
    )
    op.create_index(
        "ix_notification_deliveries_channel_created",
        "notification_deliveries",
        ["channel_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_due",
        "notification_deliveries",
        ["next_publish_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'sending')"),
    )
    op.create_index(
        "ix_check_runs_retention",
        "check_runs",
        ["completed_at"],
        unique=False,
        postgresql_where=sa.text("state IN ('completed', 'cancelled', 'infrastructure_failed')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_check_runs_retention",
        table_name="check_runs",
        postgresql_where=sa.text("state IN ('completed', 'cancelled', 'infrastructure_failed')"),
    )
    op.drop_index(
        "ix_notification_deliveries_due",
        table_name="notification_deliveries",
        postgresql_where=sa.text("status IN ('pending', 'sending')"),
    )
    op.drop_index(
        "ix_notification_deliveries_channel_created", table_name="notification_deliveries"
    )
    op.drop_table("notification_deliveries")
    op.drop_table("notification_channels")
