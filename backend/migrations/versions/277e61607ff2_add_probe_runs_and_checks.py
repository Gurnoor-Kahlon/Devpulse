"""add probe runs and checks

Revision ID: 277e61607ff2
Revises: 488e9f6fd6c1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "277e61607ff2"
down_revision: str | Sequence[str] | None = "488e9f6fd6c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "check_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("monitor_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_outcome", sa.String(length=24), nullable=True),
        sa.CheckConstraint(
            "(state = 'running' AND completed_at IS NULL AND final_outcome IS NULL) "
            "OR (state <> 'running' AND completed_at IS NOT NULL)",
            name=op.f("ck_check_runs_completion"),
        ),
        sa.CheckConstraint(
            "final_outcome IN ('success', 'failure', 'blocked', 'infrastructure_failure')",
            name=op.f("ck_check_runs_final_outcome"),
        ),
        sa.CheckConstraint(
            "state IN ('running', 'completed', 'cancelled', 'infrastructure_failed')",
            name=op.f("ck_check_runs_state"),
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled')", name=op.f("ck_check_runs_trigger")
        ),
        sa.CheckConstraint(
            "configuration_version > 0", name=op.f("ck_check_runs_configuration_version")
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"],
            ["monitors.id"],
            name=op.f("fk_check_runs_monitor_id_monitors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_check_runs")),
        sa.UniqueConstraint(
            "monitor_id", "scheduled_at", name=op.f("uq_check_runs_monitor_id_scheduled_at")
        ),
    )
    op.create_index(
        "ix_check_runs_monitor_id_scheduled_at",
        "check_runs",
        ["monitor_id", sa.literal_column("scheduled_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_check_runs_active_monitor",
        "check_runs",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("state = 'running'"),
    )
    op.create_table(
        "checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.String(length=160), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'blocked', 'infrastructure_failure')",
            name=op.f("ck_checks_outcome"),
        ),
        sa.CheckConstraint("attempt_number > 0", name=op.f("ck_checks_attempt_number")),
        sa.CheckConstraint("duration_ms >= 0", name=op.f("ck_checks_duration")),
        sa.CheckConstraint("finished_at >= started_at", name=op.f("ck_checks_time_order")),
        sa.CheckConstraint("http_status BETWEEN 100 AND 599", name=op.f("ck_checks_http_status")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["check_runs.id"],
            name=op.f("fk_checks_run_id_check_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checks")),
        sa.UniqueConstraint(
            "run_id", "attempt_number", name=op.f("uq_checks_run_id_attempt_number")
        ),
    )


def downgrade() -> None:
    op.drop_table("checks")
    op.drop_index(
        "uq_check_runs_active_monitor",
        table_name="check_runs",
        postgresql_where=sa.text("state = 'running'"),
    )
    op.drop_index("ix_check_runs_monitor_id_scheduled_at", table_name="check_runs")
    op.drop_table("check_runs")
