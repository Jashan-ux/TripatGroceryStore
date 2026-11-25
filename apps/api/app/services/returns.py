"""Returns: ask, decide, receive, credit — in that order, once.

The brief is specific about the money (C-16): **nothing is credited until the shop
has the goods back**. So ``request`` only records intent, ``decision`` only approves
or refuses, and ``receive`` is the single place that pays — into the wallet, because
cash-on-delivery orders have already been paid in cash.

Exactly-once is the database's job: ``order_returns.credited_entry_id`` is unique
and ``receive`` returns early when it is already set, so a double tap or a retried
request cannot pay twice (A-12).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import ReturnStatus, WalletReason
from app.models.orders import Order
from app.models.returns import OrderReturn, ReturnItem
from app.repositories import orders as orders_repo
from app.repositories import rewards as repo
from app.schemas.returns import (
    AdminReturnListOut,
    AdminReturnOut,
    ReturnItemOut,
    ReturnListOut,
    ReturnOut,
    ReturnRequestIn,
)
from app.services import loyalty, notifications, scratch_cards
from app.services import wallet as wallet_service

logger = get_logger(__name__)

OPEN_STATUSES = (ReturnStatus.requested, ReturnStatus.approved)


def return_out(order_return: OrderReturn, *, order_number: str = "") -> ReturnOut:
    return ReturnOut(
        id=order_return.id,
        order_id=order_return.order_id,
        order_number=order_number,
        status=order_return.status.value,
        reason=order_return.reason,
        refund_paise=order_return.refund_paise,
        decision_note=order_return.decision_note,
        requested_at=order_return.requested_at,
        decided_at=order_return.decided_at,
        received_at=order_return.received_at,
        items=[
            ReturnItemOut(
                order_item_id=item.order_item_id,
                name=item.name,
                quantity=item.quantity,
                refund_paise=item.refund_paise,
            )
            for item in order_return.items
        ],
    )


async def _order_for(session: AsyncSession, profile: Profile, order_id: uuid.UUID) -> Order:
    order = await orders_repo.get_order(session, profile.id, order_id)
    if order is None:
        raise NotFoundError("That order is not yours.", code="order_not_found")
    return order


async def _delivered_at(session: AsyncSession, order: Order) -> datetime | None:
    """When the shop marked it delivered: the return window starts there, not at order time."""
    delivered = [event.created_at for event in order.events if event.status == "delivered"]
    return max(delivered) if delivered else None


async def request_return(
    session: AsyncSession,
    profile: Profile,
    order_id: uuid.UUID,
    payload: ReturnRequestIn,
    settings: StoreSettings,
) -> ReturnOut:
    order = await _order_for(session, profile, order_id)
    if order.status.value != "delivered":
        raise ConflictError(
            "Only delivered orders can be returned.",
            code="return_order_not_delivered",
            details={"status": order.status.value},
        )

    delivered_at = await _delivered_at(session, order)
    window = timedelta(days=max(1, settings.return_window_days))
    if delivered_at is not None and datetime.now(tz=UTC) - delivered_at > window:
        raise ConflictError(
            f"Returns are accepted for {settings.return_window_days} days after delivery.",
            code="return_window_closed",
            details={
                "return_window_days": settings.return_window_days,
                "delivered_at": delivered_at.isoformat(),
            },
        )

    if await repo.get_open_return_for_order(session, order.id) is not None:
        raise ConflictError("There is already a return for this order.", code="return_already_open")

    lines = {item.id: item for item in order.items}
    chosen: list[ReturnItem] = []
    refund = 0
    for wanted in payload.items:
        line = lines.get(wanted.order_item_id)
        if line is None:
            raise ValidationError(
                "That item is not on this order.",
                code="return_item_unknown",
                details={"order_item_id": str(wanted.order_item_id)},
            )
        if wanted.quantity > line.quantity:
            raise ValidationError(
                f"You ordered {line.quantity} of {line.name}.",
                code="return_quantity_too_high",
                details={"order_item_id": str(line.id), "ordered": line.quantity},
            )
        line_refund = line.unit_price_paise * wanted.quantity
        refund += line_refund
        chosen.append(
            ReturnItem(
                order_item_id=line.id,
                name=line.name,
                quantity=wanted.quantity,
                refund_paise=line_refund,
            )
        )

    # Never refund more than the customer actually paid: a referral discount or a
    # wallet payment makes the cash out smaller than the sum of the lines.
    refund = min(refund, order.total_paise)

    order_return = OrderReturn(
        order_id=order.id,
        profile_id=profile.id,
        status=ReturnStatus.requested,
        reason=payload.reason,
        refund_paise=refund,
        requested_at=datetime.now(tz=UTC),
    )
    order_return.items.extend(chosen)
    await repo.add_return(session, order_return)
    await notifications.announce_return_requested(
        session,
        order_number=order.order_number,
        return_id=order_return.id,
        refund_paise=refund,
    )
    await session.commit()
    await session.refresh(order_return)
    logger.info(
        "return_requested",
        return_id=str(order_return.id),
        order_id=str(order.id),
        refund_paise=refund,
    )
    return return_out(order_return, order_number=order.order_number)


async def list_mine(session: AsyncSession, profile: Profile) -> ReturnListOut:
    rows = await repo.list_returns_for_profile(session, profile.id)
    out: list[ReturnOut] = []
    for row in rows:
        order = await session.get(Order, row.order_id)
        out.append(return_out(row, order_number=order.order_number if order else ""))
    return ReturnListOut(returns=out)


async def list_for_admin(
    session: AsyncSession, *, status: str | None, page: int, page_size: int
) -> AdminReturnListOut:
    rows = await repo.list_returns(
        session, status=status, limit=page_size, offset=(page - 1) * page_size
    )
    total = await repo.count_returns(session, status=status)
    items: list[AdminReturnOut] = []
    for row in rows:
        order = await session.get(Order, row.order_id)
        items.append(
            AdminReturnOut(
                **return_out(row, order_number=order.order_number if order else "").model_dump(),
                customer_name=order.customer_name if order else "",
                customer_phone=order.customer_phone if order else "",
            )
        )
    import math

    return AdminReturnListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


async def detail_for_admin(session: AsyncSession, order_return: OrderReturn) -> AdminReturnOut:
    """One return with the customer's name and phone attached for the counter."""
    order = await session.get(Order, order_return.order_id)
    base = return_out(order_return, order_number=order.order_number if order else "")
    return AdminReturnOut(
        **base.model_dump(),
        customer_name=order.customer_name if order else "",
        customer_phone=order.customer_phone if order else "",
    )


async def _notify(
    session: AsyncSession,
    order_return: OrderReturn,
    status: str,
    settings: StoreSettings,
    *,
    note: str = "",
) -> None:
    profile = await session.get(Profile, order_return.profile_id)
    order = await session.get(Order, order_return.order_id)
    if profile is None or order is None:
        return
    await notifications.announce_return_update(
        session,
        profile,
        order_number=order.order_number,
        status=status,
        refund_paise=order_return.refund_paise,
        note=note,
        return_id=order_return.id,
        settings=settings,
    )


async def decide(
    session: AsyncSession,
    return_id: uuid.UUID,
    *,
    approve: bool,
    note: str,
    actor: Profile,
    settings: StoreSettings,
) -> OrderReturn:
    order_return = await repo.get_return_for_update(session, return_id)
    if order_return is None:
        raise NotFoundError("No such return.", code="return_not_found")
    if order_return.status is not ReturnStatus.requested:
        raise ConflictError(
            "This return has already been decided.",
            code="return_already_decided",
            details={"status": order_return.status.value},
        )

    order_return.status = ReturnStatus.approved if approve else ReturnStatus.rejected
    order_return.decided_at = datetime.now(tz=UTC)
    order_return.decided_by = actor.id
    order_return.decision_note = note
    await _notify(session, order_return, order_return.status.value, settings, note=note)
    await session.commit()
    await session.refresh(order_return)
    logger.info(
        "return_decided",
        return_id=str(order_return.id),
        status=order_return.status.value,
        actor=str(actor.id),
    )
    return order_return


async def receive(
    session: AsyncSession,
    return_id: uuid.UUID,
    *,
    note: str,
    actor: Profile,
    settings: StoreSettings,
) -> OrderReturn:
    """The goods are back: restore stock, credit the wallet, close the order."""
    order_return = await repo.get_return_for_update(session, return_id)
    if order_return is None:
        raise NotFoundError("No such return.", code="return_not_found")

    # Already paid: hand back the same row instead of paying twice (A-12).
    if order_return.status is ReturnStatus.received_credited:
        return order_return
    if order_return.status is not ReturnStatus.approved:
        raise ConflictError(
            "Approve the return before marking it received.",
            code="return_not_approved",
            details={"status": order_return.status.value},
        )

    order = await repo.lock_order_for_return(session, order_return.order_id)
    if order is None:
        raise NotFoundError("No such order.", code="order_not_found")

    for line in order_return.items:
        item = next((entry for entry in order.items if entry.id == line.order_item_id), None)
        if item is None:
            continue
        if item.variant_id is not None:
            await orders_repo.restore_variant_stock(session, item.variant_id, line.quantity)
        else:
            await orders_repo.restore_product_stock(session, item.product_id, line.quantity)

    entry = await wallet_service.credit(
        session,
        order_return.profile_id,
        order_return.refund_paise,
        WalletReason.return_refund,
        note=f"Refund for {order.order_number}",
        order_id=order.id,
        return_id=order_return.id,
    )
    order_return.credited_entry_id = entry.id
    order_return.received_at = datetime.now(tz=UTC)
    order_return.status = ReturnStatus.received_credited
    order_return.decision_note = note or order_return.decision_note

    order.status = type(order.status).returned
    await orders_repo.add_event(
        session,
        order.id,
        status="returned",
        actor="admin",
        note=note or "Goods received back; refund credited to the wallet",
    )

    await scratch_cards.void_for_order(session, order.id, "Order was returned")
    profile = await session.get(Profile, order_return.profile_id)
    if profile is not None:
        # Spend is net of returns, so this can move a badge back down (silently).
        loyalty.apply_spend(profile, -abs(order_return.refund_paise), settings)

    await _notify(
        session,
        order_return,
        "received_credited",
        settings,
        note=note or "We have your items back and credited your wallet.",
    )
    await session.commit()
    await session.refresh(order_return)
    logger.info(
        "return_received_credited",
        return_id=str(order_return.id),
        refund_paise=order_return.refund_paise,
        actor=str(actor.id),
    )
    return order_return
