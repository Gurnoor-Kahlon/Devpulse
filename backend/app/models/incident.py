from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("confirmed_at >= started_at", name="confirmation_order"),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= confirmed_at", name="recovery_order"
        ),
        CheckConstraint(
            "(resolved_at IS NULL) = (recovery_evidence IS NULL)", name="recovery_evidence"
        ),
        Index(
            "uq_incidents_open_monitor",
            "monitor_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index("ix_incidents_monitor_started_id", "monitor_id", "started_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monitor_id: Mapped[UUID] = mapped_column(ForeignKey("monitors.id", ondelete="RESTRICT"))
    monitor_name: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("check_runs.id", ondelete="SET NULL")
    )
    opening_check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("checks.id", ondelete="SET NULL")
    )
    confirmation_check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("checks.id", ondelete="SET NULL")
    )
    recovery_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("check_runs.id", ondelete="SET NULL")
    )
    recovery_check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("checks.id", ondelete="SET NULL")
    )
    opening_evidence: Mapped[dict[str, object]] = mapped_column(JSONB)
    confirmation_evidence: Mapped[dict[str, object]] = mapped_column(JSONB)
    recovery_evidence: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
