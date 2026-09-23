from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Monitor(Base):
    __tablename__ = "monitors"
    __table_args__ = (
        CheckConstraint("char_length(trim(name)) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint("char_length(url) BETWEEN 1 AND 2048", name="url_length"),
        CheckConstraint("url ~ '^https?://'", name="url_scheme"),
        CheckConstraint("method IN ('GET', 'HEAD')", name="method"),
        CheckConstraint("expected_status BETWEEN 200 AND 599", name="expected_status"),
        CheckConstraint("interval_seconds BETWEEN 60 AND 86400", name="interval_seconds"),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 10", name="timeout_seconds"),
        CheckConstraint("configuration_version > 0", name="configuration_version"),
        CheckConstraint(
            "current_state IN ('unknown', 'operational', 'down', 'confirming_failure')",
            name="current_state",
        ),
        CheckConstraint("deleted_at IS NULL OR NOT enabled", name="archived_disabled"),
        CheckConstraint(
            "(enabled AND next_due_at IS NOT NULL) OR (NOT enabled AND next_due_at IS NULL)",
            name="due_when_enabled",
        ),
        Index("ix_monitors_user_id_created_at_id", "user_id", "created_at", "id"),
        Index(
            "ix_monitors_next_due_at",
            "next_due_at",
            postgresql_where=text("enabled AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2048))
    method: Mapped[str] = mapped_column(String(4), default="GET")
    expected_status: Mapped[int] = mapped_column(default=200)
    interval_seconds: Mapped[int] = mapped_column(default=60)
    timeout_seconds: Mapped[int] = mapped_column(default=5)
    enabled: Mapped[bool] = mapped_column(default=True)
    configuration_version: Mapped[int] = mapped_column(default=1)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_state: Mapped[str] = mapped_column(String(20), default="unknown")
    last_completed_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
