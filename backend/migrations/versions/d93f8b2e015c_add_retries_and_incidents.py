"""add retries and incidents

Revision ID: d93f8b2e015c
Revises: c82e7a1d904b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d93f8b2e015c"
down_revision: str | Sequence[str] | None = "c82e7a1d904b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("monitor_id", sa.Uuid(), nullable=False),
        sa.Column("monitor_name", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opening_run_id", sa.Uuid(), nullable=True),
        sa.Column("opening_check_id", sa.Uuid(), nullable=True),
        sa.Column("confirmation_check_id", sa.Uuid(), nullable=True),
        sa.Column("recovery_run_id", sa.Uuid(), nullable=True),
        sa.Column("recovery_check_id", sa.Uuid(), nullable=True),
        sa.Column("opening_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confirmation_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "recovery_evidence",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.CheckConstraint(
            "(resolved_at IS NULL) = (recovery_evidence IS NULL)",
            name=op.f("ck_incidents_recovery_evidence"),
        ),
        sa.CheckConstraint(
            "confirmed_at >= started_at", name=op.f("ck_incidents_confirmation_order")
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= confirmed_at",
            name=op.f("ck_incidents_recovery_order"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmation_check_id"],
            ["checks.id"],
            name=op.f("fk_incidents_confirmation_check_id_checks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"],
            ["monitors.id"],
            name=op.f("fk_incidents_monitor_id_monitors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opening_check_id"],
            ["checks.id"],
            name=op.f("fk_incidents_opening_check_id_checks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["opening_run_id"],
            ["check_runs.id"],
            name=op.f("fk_incidents_opening_run_id_check_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_check_id"],
            ["checks.id"],
            name=op.f("fk_incidents_recovery_check_id_checks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_run_id"],
            ["check_runs.id"],
            name=op.f("fk_incidents_recovery_run_id_check_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(
        "ix_incidents_monitor_started_id",
        "incidents",
        ["monitor_id", "started_at", "id"],
        unique=False,
    )
    op.create_index(
        "uq_incidents_open_monitor",
        "incidents",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.add_column(
        "check_runs",
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    # Preserve the attempt identity of legacy completed runs. No incidents are backfilled.
    op.execute(
        "UPDATE check_runs SET attempt_count = COALESCE("
        "(SELECT max(attempt_number) FROM checks WHERE checks.run_id = check_runs.id), 0)"
    )
    op.create_check_constraint(
        op.f("ck_check_runs_attempt_count"), "check_runs", "attempt_count BETWEEN 0 AND 3"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_check_runs_attempt_count"), "check_runs", type_="check")
    op.drop_column("check_runs", "attempt_count")
    op.drop_index(
        "uq_incidents_open_monitor",
        table_name="incidents",
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.drop_index("ix_incidents_monitor_started_id", table_name="incidents")
    op.drop_table("incidents")
