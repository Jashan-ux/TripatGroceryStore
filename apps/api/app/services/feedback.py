"""Customer feedback: kept in the database, announced to the shop, and emailable.

A message must not depend on an email provider being configured — the row is the
source of truth, the bell is the fast signal, and the email is a convenience. That
order matters: if Resend is down or unset, the owner still sees the message.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.admin import Feedback
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import FeedbackKind, FeedbackStatus, NotificationKind
from app.models.notifications import Notification
from app.repositories import admin_tools as repo
from app.schemas.admin_ops import FeedbackIn, FeedbackOut
from app.services import email


def feedback_out(row: Feedback, *, customer_name: str = "") -> FeedbackOut:
    return FeedbackOut(
        id=row.id,
        name=row.name,
        phone=row.phone,
        email=row.email,
        kind=row.kind.value,
        message=row.message,
        status=row.status.value,
        read_at=row.read_at,
        created_at=row.created_at,
        customer_name=customer_name,
    )


async def submit(
    session: AsyncSession,
    *,
    payload: FeedbackIn,
    user: Profile | None,
    settings: StoreSettings,
) -> FeedbackOut:
    """Store the message, ring the shop's bell, and queue the email."""
    name = payload.name.strip() or (user.name if user else "")
    email_address = payload.email.strip() or (user.email if user else "")
    phone = payload.phone.strip() or ((user.phone or "") if user else "")

    row = Feedback(
        profile_id=user.id if user else None,
        name=name[:120],
        phone=phone[:20],
        email=email_address[:320],
        kind=FeedbackKind(payload.kind),
        message=payload.message.strip(),
        status=FeedbackStatus.new,
    )
    await repo.add_feedback(session, row)

    who = name or "A customer"
    for profile_id, _email in await repo.admin_profiles(session):
        session.add(
            Notification(
                profile_id=profile_id,
                kind=NotificationKind.system,
                title=f"New feedback from {who}"[:140],
                body=row.message[:500],
                href="/admin/feedback",
                order_id=None,
            )
        )
    await session.flush()

    if settings.feedback_email:
        await email.queue(
            session,
            to=settings.feedback_email,
            subject=f"Feedback from {who} ({row.kind.value})"[:200],
            body="\n".join(
                [
                    f"From: {who}",
                    f"Phone: {phone or '—'}",
                    f"Email: {email_address or '—'}",
                    f"About: {row.kind.value}",
                    "",
                    row.message,
                    "",
                    f"{settings.store_name} · {settings.store_phone}",
                ]
            ),
            dedupe_key=f"feedback:{row.id}",
        )

    return feedback_out(row, customer_name=name)


async def list_page(
    session: AsyncSession, *, status: FeedbackStatus | None, page: int, page_size: int
) -> tuple[list[FeedbackOut], int]:
    rows, total = await repo.list_feedback(session, status=status, page=page, page_size=page_size)
    return [feedback_out(row) for row in rows], total


async def mark_read(
    session: AsyncSession, *, feedback_id: uuid.UUID, actor: Profile
) -> FeedbackOut:
    row = await repo.get_feedback(session, feedback_id)
    if row is None:
        raise NotFoundError("That message does not exist.", code="feedback_not_found")
    if row.status is not FeedbackStatus.read:
        row.status = FeedbackStatus.read
        row.read_at = datetime.now(tz=UTC)
        row.read_by = actor.id
        await session.flush()
    return feedback_out(row, customer_name=row.name)


__all__ = ["feedback_out", "list_page", "mark_read", "submit"]
