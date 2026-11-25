"""Offers: one message, sent to everyone or to one loyalty tier, with a reach count.

What "sent" means here is deliberately modest, because promises should match
reality: a row in every matching customer's bell, an email in the outbox for each
of them, and a banner row the storefront can show. Web push is wired but belongs
to Phase 7 — the row is created now so push can join in later without a schema
change.

The count is recorded, not estimated: ``recipients`` is how many bells rang and
``emails_queued`` is how many addresses went into the outbox, both visible in the
history so the owner can see what actually happened.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Offer
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import NotificationKind, OfferAudience
from app.models.notifications import Notification
from app.repositories import admin_tools as repo
from app.schemas.admin_ops import OfferIn, OfferOut
from app.services import audit, email


def audience_label(audience: OfferAudience) -> str:
    return {
        OfferAudience.all: "every customer",
        OfferAudience.gold: "Gold members",
        OfferAudience.platinum: "Platinum members",
        OfferAudience.diamond: "Diamond members",
    }[audience]


def offer_out(offer: Offer) -> OfferOut:
    return OfferOut(
        id=offer.id,
        title=offer.title,
        body=offer.body,
        href=offer.href,
        audience=offer.audience.value,
        is_active=offer.is_active,
        expires_at=offer.expires_at,
        recipients=offer.recipients,
        emails_queued=offer.emails_queued,
        sent_at=offer.sent_at,
        created_at=offer.created_at,
    )


def _email_body(offer: Offer, settings: StoreSettings) -> str:
    lines = [
        offer.title,
        "",
        offer.body or "(no further details)",
        "",
        f"See it in the app: {settings.store_name}",
        "",
        f"{settings.store_name} · {settings.store_phone}",
        settings.store_address,
    ]
    return "\n".join(lines)


async def send(
    session: AsyncSession,
    actor: Profile,
    payload: OfferIn,
    settings: StoreSettings,
) -> Offer:
    audience = OfferAudience(payload.audience)
    offer = Offer(
        title=payload.title.strip(),
        body=payload.body.strip(),
        href=payload.href,
        audience=audience,
        expires_at=payload.expires_at,
        sent_by=actor.id,
        recipients=0,
        emails_queued=0,
    )
    session.add(offer)
    await session.flush()

    tier = None if audience is OfferAudience.all else audience.value
    people = await repo.audience_emails(session, tier=tier)

    for profile_id, _email, _name in people:
        session.add(
            Notification(
                profile_id=profile_id,
                kind=NotificationKind.offer,
                title=offer.title[:140],
                body=offer.body[:1000],
                href=offer.href,
                order_id=None,
            )
        )
    await session.flush()

    queued = 0
    for _profile_id, address, _name in people:
        if not address:
            continue
        row = await email.queue(
            session,
            to=address,
            subject=f"{settings.store_name}: {offer.title}",
            body=_email_body(offer, settings),
            dedupe_key=f"offer:{offer.id}:{address.lower()}",
        )
        if row is not None:
            queued += 1

    offer.recipients = len(people)
    offer.emails_queued = queued
    await session.flush()

    await audit.record(
        session,
        actor=actor,
        action="offer.sent",
        entity="offer",
        entity_id=offer.id,
        summary=offer.title,
        after={
            "title": offer.title,
            "audience": audience.value,
            "recipients": offer.recipients,
            "emails_queued": offer.emails_queued,
        },
    )
    return offer


async def current(session: AsyncSession) -> Offer | None:
    return await repo.current_offer(session, datetime.now(tz=UTC))


async def list_page(
    session: AsyncSession, *, page: int, page_size: int
) -> tuple[list[OfferOut], int]:
    rows, total = await repo.list_offers(session, page=page, page_size=page_size)
    return [offer_out(row) for row in rows], total


__all__ = ["audience_label", "current", "list_page", "offer_out", "send"]
