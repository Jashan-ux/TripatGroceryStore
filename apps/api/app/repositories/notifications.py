"""Database access for notifications and the email outbox.

Both tables are append-mostly: a notification is written once and only ever gets
``read_at``; an email moves through ``status``. Reads are always scoped to one
profile, so the same rule as addresses and orders applies — there is no query that
can hand a customer somebody else's bell.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import Profile
from app.models.enums import EmailStatus, UserRole
from app.models.notifications import EmailMessage, Notification


async def add_notification(session: AsyncSession, notification: Notification) -> Notification:
    session.add(notification)
    await session.flush()
    return notification


async def list_notifications(
    session: AsyncSession, profile_id: uuid.UUID, *, limit: int, offset: int
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.profile_id == profile_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(stmt)).all())


async def count_notifications(session: AsyncSession, profile_id: uuid.UUID) -> int:
    stmt = (
        select(func.count()).select_from(Notification).where(Notification.profile_id == profile_id)
    )
    return int(await session.scalar(stmt) or 0)


async def count_unread(session: AsyncSession, profile_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.profile_id == profile_id, Notification.read_at.is_(None))
    )
    return int(await session.scalar(stmt) or 0)


async def get_notification(
    session: AsyncSession, profile_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification | None:
    stmt = select(Notification).where(
        Notification.id == notification_id, Notification.profile_id == profile_id
    )
    return cast("Notification | None", await session.scalar(stmt))


async def mark_all_read(session: AsyncSession, profile_id: uuid.UUID, when: datetime) -> int:
    stmt = (
        update(Notification)
        .where(Notification.profile_id == profile_id, Notification.read_at.is_(None))
        .values(read_at=when)
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def list_admin_profiles(session: AsyncSession) -> list[Profile]:
    """Everyone who should hear about a new order."""
    stmt = select(Profile).where(Profile.role == UserRole.admin)
    return list((await session.scalars(stmt)).all())


async def queue_email(session: AsyncSession, message: EmailMessage) -> EmailMessage:
    """Add an email to the outbox.

    The caller checks ``email_exists`` first; the unique ``dedupe_key`` is the
    backstop. A duplicate insert therefore aborts a transaction rather than being
    swallowed — this is an outbox inside an order transaction, and a silent
    ``rollback()`` here would discard the order that was just placed.
    """
    session.add(message)
    await session.flush()
    return message


async def email_exists(session: AsyncSession, dedupe_key: str) -> bool:
    stmt = (
        select(func.count()).select_from(EmailMessage).where(EmailMessage.dedupe_key == dedupe_key)
    )
    return bool(await session.scalar(stmt))


async def pending_emails(session: AsyncSession, *, limit: int = 25) -> list[EmailMessage]:
    stmt = (
        select(EmailMessage)
        .where(EmailMessage.status == EmailStatus.queued)
        .order_by(EmailMessage.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list((await session.scalars(stmt)).all())
