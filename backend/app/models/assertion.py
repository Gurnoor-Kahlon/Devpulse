from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Assertion(Base):
    __tablename__ = "assertions"
    __table_args__ = (
        UniqueConstraint("monitor_id", "position"),
        CheckConstraint("position BETWEEN 0 AND 9", name="position"),
        CheckConstraint("kind IN ('text_contains', 'json_equals')", name="kind"),
        CheckConstraint("char_length(pointer) <= 512", name="pointer_length"),
        CheckConstraint(
            "jsonb_typeof(expected) IN ('string', 'number', 'boolean', 'null')", name="scalar"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    monitor_id: Mapped[UUID] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"))
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    pointer: Mapped[str] = mapped_column(String(512))
    expected: Mapped[object] = mapped_column(JSONB, nullable=False)
