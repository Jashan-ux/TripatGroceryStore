"""Scratch cards: earned by a big order, unlocked by its delivery, rubbed off once.

The prize is drawn **when the card is created** and stored, so the same card always
pays the same amount and the client can never influence it. Until ``reveal`` the
API reports ``amount_paise = None``; revealing moves the money into the wallet and
stamps ``credited_entry_id``, which is unique in the database, so a double tap
cannot pay twice.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import ScratchCardStatus, WalletReason
from app.models.orders import Order
from app.models.rewards import ScratchCard
from app.repositories import rewards as repo
from app.schemas.rewards import ScratchCardListOut, ScratchCardOut, ScratchRevealOut
from app.services import wallet as wallet_service

logger = get_logger(__name__)

#: Prizes are whole rupees, so the copy can say "₹75" and not "₹74.63".
PRIZE_STEP_PAISE = 100


def draw_amount_paise(settings: StoreSettings) -> int:
    """A prize inside the configured range, decided here and never by the request."""
    low = settings.scratch_min_paise
    high = max(settings.scratch_max_paise, low)
    steps = (high - low) // PRIZE_STEP_PAISE
    return low + secrets.randbelow(steps + 1) * PRIZE_STEP_PAISE


def card_out(card: ScratchCard, *, order_number: str = "") -> ScratchCardOut:
    revealed = card.status in {
        ScratchCardStatus.revealed,
        ScratchCardStatus.used,
    }
    return ScratchCardOut(
        id=card.id,
        status=card.status.value,
        threshold_paise=card.threshold_paise,
        # The whole point: the amount is withheld until the customer rubs it off.
        amount_paise=card.amount_paise if revealed else None,
        order_id=card.order_id,
        order_number=order_number,
        unlocked_at=card.unlocked_at,
        expires_at=card.expires_at,
        revealed_at=card.revealed_at,
        created_at=card.created_at,
    )


async def create_for_order(
    session: AsyncSession, order: Order, settings: StoreSettings
) -> ScratchCard | None:
    """A card for an order past the threshold; ``None`` for the ordinary ones."""
    if order.subtotal_paise < settings.scratch_threshold_paise:
        return None
    card = ScratchCard(
        profile_id=order.profile_id,
        order_id=order.id,
        status=ScratchCardStatus.locked,
        threshold_paise=settings.scratch_threshold_paise,
        amount_paise=draw_amount_paise(settings),
    )
    await repo.add_card(session, card)
    logger.info(
        "scratch_card_created",
        order_id=str(order.id),
        card_id=str(card.id),
        threshold_paise=settings.scratch_threshold_paise,
    )
    return card


async def unlock_for_order(
    session: AsyncSession, order: Order, settings: StoreSettings
) -> ScratchCard | None:
    """Delivered: the card can be rubbed off, for a while."""
    card = await repo.get_card_for_order(session, order.id)
    if card is None or card.status is not ScratchCardStatus.locked:
        return None
    now = datetime.now(tz=UTC)
    card.status = ScratchCardStatus.ready
    card.unlocked_at = now
    card.expires_at = now + timedelta(days=max(1, settings.scratch_expiry_days))
    logger.info("scratch_card_unlocked", card_id=str(card.id), order_id=str(order.id))
    return card


async def void_for_order(session: AsyncSession, order_id: uuid.UUID, reason: str) -> None:
    """The order came back (or was called off) before the card was used."""
    card = await repo.get_card_for_order(session, order_id)
    if card is None or card.status not in {ScratchCardStatus.locked, ScratchCardStatus.ready}:
        return
    card.status = ScratchCardStatus.void
    card.void_reason = reason[:80]
    logger.info("scratch_card_void", card_id=str(card.id), reason=reason)


def _expire(card: ScratchCard) -> bool:
    if (card.status is ScratchCardStatus.ready) and (
        card.expires_at is not None and card.expires_at <= datetime.now(tz=UTC)
    ):
        card.status = ScratchCardStatus.void
        card.void_reason = "Expired before it was revealed"
        return True
    return False


async def list_cards(session: AsyncSession, profile: Profile) -> ScratchCardListOut:
    cards = await repo.list_cards(session, profile.id)
    changed = False
    for card in cards:
        changed = _expire(card) or changed
    if changed:
        await session.commit()
    out = [card_out(card) for card in cards]
    counts = await repo.count_cards(session, profile.id)
    return ScratchCardListOut(
        cards=out,
        ready=counts.get("ready", 0),
        locked=counts.get("locked", 0),
        revealed=counts.get("revealed", 0),
    )


async def reveal(session: AsyncSession, profile: Profile, card_id: uuid.UUID) -> ScratchRevealOut:
    card = await repo.get_card_for_update(session, profile.id, card_id)
    if card is None:
        raise NotFoundError("No such scratch card.", code="scratch_card_not_found")

    if card.status is ScratchCardStatus.revealed or card.status is ScratchCardStatus.used:
        raise ConflictError(
            "This card has already been revealed.",
            code="scratch_card_used",
            details={"amount_paise": card.amount_paise},
        )
    if card.status is ScratchCardStatus.void:
        raise ConflictError(
            "This card is no longer valid.",
            code="scratch_card_void",
            details={"reason": card.void_reason},
        )
    if _expire(card):
        await session.commit()
        raise ConflictError(
            "This card expired before it was revealed.",
            code="scratch_card_expired",
            details={"expires_at": card.expires_at.isoformat() if card.expires_at else None},
        )
    if card.status is ScratchCardStatus.locked:
        raise ConflictError(
            "This card unlocks when the order is delivered.",
            code="scratch_card_locked",
            details={"order_id": str(card.order_id)},
        )

    card.reveal_attempts += 1
    card.status = ScratchCardStatus.revealed
    card.revealed_at = datetime.now(tz=UTC)
    entry = await wallet_service.credit(
        session,
        profile.id,
        card.amount_paise,
        WalletReason.scratch_card,
        note="Scratch card winnings",
        scratch_card_id=card.id,
    )
    card.credited_entry_id = entry.id
    await session.commit()
    await session.refresh(card)
    logger.info(
        "scratch_card_revealed",
        card_id=str(card.id),
        amount_paise=card.amount_paise,
        profile_id=str(profile.id),
    )
    return ScratchRevealOut(
        card=card_out(card),
        credited_paise=card.amount_paise,
        wallet_balance_paise=await wallet_service.balance(session, profile.id),
    )
