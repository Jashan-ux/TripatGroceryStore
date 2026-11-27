"""In-app notifications and the email outbox (Phase 3).

Two rules shape this schema:

* A notification belongs to **one profile** and is written in the same
  transaction as the thing it describes. If the order commits, the bell rings; if
  the order rolls back, nothing is announced.
* Email is *queued*, never sent inline. The checkout commits first, then a
  background flush drains the queue, so a mail provider having a bad minute can
  never fail an order. ``dedupe_key`` makes that flush idempotent.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import EmailStatus, NotificationKind


def _kind_enum() -> SAEnum:
    return SAEnum(
        NotificationKind, name="notification_kind", values_callable=lambda e: [m.value for m in e]
    )


def _email_status_enum() -> SAEnum:
    return SAEnum(EmailStatus, name="email_status", values_callable=lambda e: [m.value for m in e])


class Notification(Base, TimestampMixin):
    """One line in one person's bell."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_profile_created", "profile_id", "created_at"),
        Index("ix_notifications_unread", "profile_id", "read_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[NotificationKind] = mapped_column(_kind_enum(), nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    #: Where tapping it should go, e.g. ``/orders/<uuid>``.
    href: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailMessage(Base, TimestampMixin):
    """An email waiting for (or finished with) the provider."""

    __tablename__ = "email_messages"
    __table_args__ = (Index("ix_email_messages_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[EmailStatus] = mapped_column(
        _email_status_enum(), nullable=False, server_default=text("'queued'::email_status")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    #: Idempotency for the flush: the same key can only ever be queued once.
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["EmailMessage", "Notification"]
