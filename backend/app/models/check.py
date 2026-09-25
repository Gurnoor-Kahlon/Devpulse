from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CheckRun(Base):
    __tablename__ = "check_runs"
    __table_args__ = (
        UniqueConstraint("monitor_id", "scheduled_at"),
        CheckConstraint("configuration_version > 0", name="configuration_version"),
        CheckConstraint("trigger IN ('manual', 'scheduled')", name="trigger"),
        CheckConstraint(
            "state IN ('running', 'completed', 'cancelled', 'infrastructure_failed')", name="state"
        ),
        CheckConstraint(
            "final_outcome IN ('success', 'failure', 'blocked', 'infrastructure_failure')",
            name="final_outcome",
        ),
        CheckConstraint(
            "(state = 'running' AND completed_at IS NULL AND final_outcome IS NULL) "
            "OR (state <> 'running' AND completed_at IS NOT NULL)",
            name="completion",
        ),
        Index("ix_check_runs_monitor_id_scheduled_at", "monitor_id", text("scheduled_at DESC")),
        Index(
            "uq_check_runs_active_monitor",
            "monitor_id",
            unique=True,
            postgresql_where=text("state = 'running'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monitor_id: Mapped[UUID] = mapped_column(ForeignKey("monitors.id", ondelete="RESTRICT"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    configuration_version: Mapped[int]
    trigger: Mapped[str] = mapped_column(String(10), default="manual")
    state: Mapped[str] = mapped_column(String(24), default="running")
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
