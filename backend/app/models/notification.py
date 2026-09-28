from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import now_utc
from app.db.base import Base


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    __table_args__ = (CheckConstraint("configuration_version > 0", name="version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    enabled: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    on_open: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    on_recovery: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    configuration_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("incident_id", "transition", "channel_id"),
        CheckConstraint("transition IN ('opened', 'resolved')", name="transition"),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')", name="status"
        ),
        CheckConstraint("attempt_count BETWEEN 0 AND 5", name="attempt_count"),
        CheckConstraint(
            "(status = 'pending' AND next_attempt_at IS NOT NULL AND lease_token IS NULL "
            "AND lease_expires_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'sending' AND next_attempt_at IS NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND completed_at IS NULL) OR "
            "(status IN ('sent', 'failed', 'cancelled') AND next_attempt_at IS NULL "
            "AND lease_token IS NULL AND lease_expires_at IS NULL AND completed_at IS NOT NULL)",
            name="lifecycle",
        ),
        Index(
            "ix_notification_deliveries_due",
            "next_publish_at",
            postgresql_where=text("status IN ('pending', 'sending')"),
        ),
        Index("ix_notification_deliveries_channel_created", "channel_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    channel_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="RESTRICT")
    )
    transition: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(
        String(10), default="pending", server_default=text("'pending'")
    )
    cancel_requested: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    attempt_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    next_publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(32))
