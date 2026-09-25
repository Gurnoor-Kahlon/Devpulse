"""Add pending runs and fenced worker leases.

Revision ID: b31d8e0c6a10
Revises: 277e61607ff2
"""

import sqlalchemy as sa
from alembic import op

revision = "b31d8e0c6a10"
down_revision = "277e61607ff2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_check_runs_state"), "check_runs", type_="check")
    op.drop_constraint(op.f("ck_check_runs_completion"), "check_runs", type_="check")
    op.drop_index("uq_check_runs_active_monitor", table_name="check_runs")
    op.add_column("check_runs", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("check_runs", sa.Column("lease_token", sa.Uuid()))
    op.add_column("check_runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    # Stop old manual executors before migration. Unfinished work becomes recoverable.
    op.execute(
        "UPDATE check_runs SET state = 'pending', next_attempt_at = CURRENT_TIMESTAMP "
        "WHERE state = 'running'"
    )
    op.create_check_constraint(
        op.f("ck_check_runs_state"),
        "check_runs",
        "state IN ('pending', 'running', 'completed', 'cancelled', 'infrastructure_failed')",
    )
    op.create_check_constraint(
        op.f("ck_check_runs_completion"),
        "check_runs",
        "(state IN ('pending', 'running') AND completed_at IS NULL AND final_outcome IS NULL) "
        "OR (state NOT IN ('pending', 'running') AND completed_at IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_check_runs_lease"),
        "check_runs",
        "(state = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
        "AND next_attempt_at IS NULL) OR (state = 'pending' AND lease_token IS NULL "
        "AND lease_expires_at IS NULL AND next_attempt_at IS NOT NULL) OR "
        "(state NOT IN ('pending', 'running') AND lease_token IS NULL "
        "AND lease_expires_at IS NULL AND next_attempt_at IS NULL)",
    )
    op.create_index(
        "uq_check_runs_active_monitor",
        "check_runs",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('pending', 'running')"),
    )
    op.create_index(
        "ix_check_runs_pending",
        "check_runs",
        ["next_attempt_at"],
        postgresql_where=sa.text("state = 'pending'"),
    )
    op.create_index(
        "ix_check_runs_expired_lease",
        "check_runs",
        ["lease_expires_at"],
        postgresql_where=sa.text("state = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("ix_check_runs_expired_lease", table_name="check_runs")
    op.drop_index("ix_check_runs_pending", table_name="check_runs")
    op.drop_index("uq_check_runs_active_monitor", table_name="check_runs")
    for name in ("lease", "completion", "state"):
        op.drop_constraint(op.f(f"ck_check_runs_{name}"), "check_runs", type_="check")
    op.execute("UPDATE check_runs SET state = 'running' WHERE state = 'pending'")
    for name in ("next_attempt_at", "lease_token", "lease_expires_at"):
        op.drop_column("check_runs", name)
    op.create_check_constraint(
        op.f("ck_check_runs_state"),
        "check_runs",
        "state IN ('running', 'completed', 'cancelled', 'infrastructure_failed')",
    )
    op.create_check_constraint(
        op.f("ck_check_runs_completion"),
        "check_runs",
        "(state = 'running' AND completed_at IS NULL AND final_outcome IS NULL) "
        "OR (state <> 'running' AND completed_at IS NOT NULL)",
    )
    op.create_index(
        "uq_check_runs_active_monitor",
        "check_runs",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("state = 'running'"),
    )
