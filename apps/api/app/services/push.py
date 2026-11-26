"""Browser push registration and delivery (Phase 7).

The browser endpoint and its encryption keys are credentials. This service is the
only place that reads them, stores them, or passes them to pywebpush; API responses
only say enabled/disabled. Offers and order updates are delivered only after the
owning transaction commits, in FastAPI's background task.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.catalogue import Profile
from app.models.enums import LoyaltyTier, OfferAudience
from app.models.push import PushSubscription

logger = get_logger(__name__)


def push_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


async def register(
    session: AsyncSession,
    profile: Profile,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    expires_at: Any = None,
) -> None:
    statement = insert(PushSubscription).values(
        profile_id=profile.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        expires_at=expires_at,
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_push_subscriptions_endpoint",
            set_={
                "profile_id": profile.id,
                "p256dh": p256dh,
                "auth": auth,
                "expires_at": expires_at,
            },
        )
    )


async def unregister(session: AsyncSession, profile: Profile, endpoint: str) -> bool:
    result = await session.execute(
        delete(PushSubscription).where(
            PushSubscription.profile_id == profile.id,
            PushSubscription.endpoint == endpoint,
        )
    )
    return bool(result.rowcount)


async def enabled(session: AsyncSession, profile: Profile) -> bool:
    return bool(
        await session.scalar(
            select(PushSubscription.id).where(PushSubscription.profile_id == profile.id).limit(1)
        )
    )


async def offer_targets(session: AsyncSession, audience: OfferAudience) -> list[dict[str, str]]:
    if not push_is_configured():
        return []
    query = (
        select(PushSubscription.endpoint, PushSubscription.p256dh, PushSubscription.auth)
        .join(Profile, Profile.id == PushSubscription.profile_id)
        .where(Profile.role == "customer")
    )
    if audience is not OfferAudience.all:
        tier = {
            OfferAudience.gold: LoyaltyTier.gold,
            OfferAudience.platinum: LoyaltyTier.platinum,
            OfferAudience.diamond: LoyaltyTier.diamond,
        }[audience]
        query = query.where(Profile.loyalty_tier == tier)
    rows = (await session.execute(query)).all()
    return [
        {"endpoint": endpoint, "p256dh": p256dh, "auth": auth} for endpoint, p256dh, auth in rows
    ]


def _send_one(subscription: dict[str, str], payload: str) -> bool:
    """Blocking pywebpush call, executed in a worker thread."""
    from pywebpush import WebPushException, webpush

    settings = get_settings()
    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
            },
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=60 * 60,
            timeout=10,
        )
        return True
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in {404, 410}:
            endpoint = subscription["endpoint"]
            # Expired endpoints are deleted after the send call in the async owner.
            raise ExpiredSubscription(endpoint) from exc
        logger.warning("web_push_delivery_failed", status=status_code or "unknown")
        return False
    except Exception as exc:  # provider/network failures must not break the offer
        logger.warning("web_push_delivery_failed", error=type(exc).__name__)
        return False


class ExpiredSubscription(Exception):
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        super().__init__("push subscription expired")


async def deliver_offer(
    subscriptions: Sequence[dict[str, str]], *, title: str, body: str, href: str
) -> int:
    """Deliver an offer to opted-in devices, pruning endpoints the provider retired."""
    if not subscriptions or not push_is_configured():
        return 0
    payload = json.dumps({"title": title[:140], "body": body[:240], "href": href})
    sessionmaker = get_sessionmaker()
    semaphore = asyncio.Semaphore(10)

    async def send_one(subscription: dict[str, str]) -> tuple[bool, str | None]:
        try:
            async with semaphore:
                return await asyncio.to_thread(_send_one, subscription, payload), None
        except ExpiredSubscription as exc:
            return False, exc.endpoint

    # Keep provider calls bounded so a large audience cannot starve the API
    # worker, while still avoiding one network round-trip per device serially.
    results: list[tuple[bool, str | None]] = []
    for offset in range(0, len(subscriptions), 50):
        batch = subscriptions[offset : offset + 50]
        results.extend(await asyncio.gather(*(send_one(subscription) for subscription in batch)))

    expired = [endpoint for _sent, endpoint in results if endpoint is not None]
    if expired:
        async with sessionmaker() as session:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.endpoint.in_(expired))
            )
            await session.commit()
    return sum(sent for sent, _endpoint in results)


async def deliver_to_profile(profile_id: uuid.UUID, *, title: str, body: str, href: str) -> int:
    """Send one post-commit order update to every device opted in by this profile."""
    if not push_is_configured():
        return 0
    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(
                select(
                    PushSubscription.endpoint, PushSubscription.p256dh, PushSubscription.auth
                ).where(PushSubscription.profile_id == profile_id)
            )
        ).all()
    targets = [
        {"endpoint": endpoint, "p256dh": p256dh, "auth": auth} for endpoint, p256dh, auth in rows
    ]
    return await deliver_offer(targets, title=title, body=body, href=href)
