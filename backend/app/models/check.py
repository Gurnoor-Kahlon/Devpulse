from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import now_utc
from app.db.base import Base


class CheckRun(Base):
    __tablename__ = "check_runs"
    __table_args__ = (
        UniqueConstraint("monitor_id", "scheduled_at"),
        CheckConstraint("configuration_version > 0", name="configuration_version"),
        CheckConstraint("attempt_count BETWEEN 0 AND 3", name="attempt_count"),
        CheckConstraint("trigger IN ('manual', 'scheduled')", name="trigger"),
        CheckConstraint(
            "state IN ('pending', 'running', 'completed', 'cancelled', 'infrastructure_failed')",
            name="state",
        ),
        CheckConstraint(
            "final_outcome IN ('success', 'failure', 'blocked', 'infrastructure_failure')",
            name="final_outcome",
        ),
        CheckConstraint(
            "(state IN ('pending', 'running') AND completed_at IS NULL AND final_outcome IS NULL) "
            "OR (state NOT IN ('pending', 'running') AND completed_at IS NOT NULL)",
            name="completion",
        ),
        CheckConstraint(
            "(state = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND next_attempt_at IS NULL) OR (state = 'pending' AND lease_token IS NULL "
            "AND lease_expires_at IS NULL AND next_attempt_at IS NOT NULL) OR "
            "(state NOT IN ('pending', 'running') AND lease_token IS NULL "
            "AND lease_expires_at IS NULL AND next_attempt_at IS NULL)",
            name="lease",
        ),
        Index(
            "ix_check_runs_pending", "next_attempt_at", postgresql_where=text("state = 'pending'")
        ),
        Index(
            "ix_check_runs_expired_lease",
            "lease_expires_at",
            postgresql_where=text("state = 'running'"),
        ),
        Index(
            "ix_check_runs_publication",
            "next_publish_at",
            postgresql_where=text("state IN ('pending', 'running')"),
        ),
        Index("ix_check_runs_monitor_id_scheduled_at", "monitor_id", text("scheduled_at DESC")),
        Index(
            "uq_check_runs_active_monitor",
            "monitor_id",
            unique=True,
            postgresql_where=text("state IN ('pending', 'running')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monitor_id: Mapped[UUID] = mapped_column(ForeignKey("monitors.id", ondelete="RESTRICT"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    configuration_version: Mapped[int]
    attempt_count: Mapped[int] = mapped_column(server_default=text("0"), default=0)
    trigger: Mapped[str] = mapped_column(String(10), default="manual")
    state: Mapped[str] = mapped_column(String(24), default="pending")
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_publish_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_outcome: Mapped[str | None] = mapped_column(String(24))


class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (
        UniqueConstraint("run_id", "attempt_number"),
        CheckConstraint("attempt_number > 0", name="attempt_number"),
        CheckConstraint("finished_at >= started_at", name="time_order"),
        CheckConstraint("duration_ms >= 0", name="duration"),
        CheckConstraint("http_status BETWEEN 100 AND 599", name="http_status"),
        CheckConstraint(
            "outcome IN ('success', 'failure', 'blocked', 'infrastructure_failure')", name="outcome"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("check_runs.id", ondelete="CASCADE"))
    attempt_number: Mapped[int] = mapped_column(default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(24))
    http_status: Mapped[int | None]
    duration_ms: Mapped[float]
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(160))

    assertion_results: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
