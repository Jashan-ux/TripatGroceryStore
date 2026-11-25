"""Transactional email, with the provider kept at arm's length.

Design rules:

* **Queue, never send inline.** A checkout writes email rows in the same
  transaction as the order, so the receipt and the announcement commit together.
  A provider outage can therefore never fail an order.
* **Flush after commit.** ``schedule_flush()`` starts a background task with its
  own session; the request has already returned 201 by the time Resend is called.
* **Honest when unconfigured.** With no ``RESEND_API_KEY`` the message is marked
  ``skipped`` with the reason recorded — not silently dropped, not retried
  forever. The owner can see exactly what would have gone out.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.enums import EmailStatus
from app.models.notifications import EmailMessage
from app.repositories import notifications as repo

logger = get_logger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
_SEND_TIMEOUT_SECONDS = 10.0

#: Strong references to in-flight flushes. Without this the event loop may
#: garbage-collect a task that nothing awaits, and the email silently never sends.
_background_tasks: set[asyncio.Task[None]] = set()


async def queue(
    session: AsyncSession,
    *,
    to: str,
    subject: str,
    body: str,
    dedupe_key: str | None = None,
) -> EmailMessage | None:
    """Add one email to the outbox (idempotent on ``dedupe_key``)."""
    if not to:
        return None
    if dedupe_key and await repo.email_exists(session, dedupe_key):
        return None
    message = EmailMessage(
        to_email=to.strip().lower(),
        subject=subject[:200],
        body_text=body,
        status=EmailStatus.queued,
        dedupe_key=dedupe_key,
    )
    return await repo.queue_email(session, message)


def schedule_flush() -> None:
    """Fire-and-forget drain of the outbox, after the response is on its way."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover - no loop in a sync context
        return
    task = loop.create_task(_flush_in_own_session())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _flush_in_own_session() -> None:
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            counts = await flush(session)
            if counts.get("sent") or counts.get("failed"):
                logger.info("email_flush", **counts)
    except Exception:  # pragma: no cover - never let mail break a request
        logger.exception("email_flush_failed")


async def flush(
    session: AsyncSession,
    *,
    limit: int = 25,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Send everything queued. Safe to call twice; safe to call with no provider.

    ``client`` is a seam for tests (an ``httpx`` client with a mock transport);
    production leaves it ``None`` and a short-lived client is created here.
    """
    settings = get_settings()
    messages = await repo.pending_emails(session, limit=limit)
    counts = {"sent": 0, "skipped": 0, "failed": 0}
    if not messages:
        return counts

    if not settings.RESEND_API_KEY:
        for message in messages:
            message.status = EmailStatus.skipped
            message.last_error = "No email provider configured (RESEND_API_KEY is empty)"
            counts["skipped"] += 1
        await session.commit()
        logger.info("email_flush_skipped", count=counts["skipped"])
        return counts

    owns_client = client is None
    sender = client or httpx.AsyncClient(timeout=_SEND_TIMEOUT_SECONDS)
    try:
        for message in messages:
            message.attempts += 1
            try:
                response = await sender.post(
                    RESEND_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.SUPPORT_EMAIL_FROM,
                        "to": [message.to_email],
                        "subject": message.subject,
                        "text": message.body_text,
                    },
                )
                if response.status_code in {200, 201, 202}:
                    message.status = EmailStatus.sent
                    message.sent_at = datetime.now(tz=UTC)
                    message.last_error = ""
                    counts["sent"] += 1
                else:
                    message.status = EmailStatus.failed
                    message.last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    counts["failed"] += 1
            except httpx.HTTPError as error:
                message.status = EmailStatus.failed
                message.last_error = f"{type(error).__name__}: {error}"[:500]
                counts["failed"] += 1
    finally:
        if owns_client:
            await sender.aclose()
    await session.commit()
    return counts
