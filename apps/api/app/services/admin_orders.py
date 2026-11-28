"""Owner-side order operations: the queue, one order, and status transitions.

The transition table lives here (not in the route) because it is the shop's
business rule, and because two of the transitions have side effects the API must
perform atomically with the status change:

* leaving ``processing`` for ``cancelled`` puts the stock back on the shelf;
* reaching ``delivered`` settles the cash-on-delivery payment.

Anything else is a hard ``409`` that says what the order is doing instead.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.catalogue import Profile
from app.models.enums import OrderStatus, PaymentStatus, UserRole
from app.models.orders import Order
from app.repositories import orders as repo
from app.schemas.admin_orders import (
    AdminOrderDeliveryIn,
    AdminOrderListOut,
    AdminOrderStatusIn,
    AdminOrderSummaryOut,
)
from app.schemas.orders import OrderOut
from app.services import email as email_service
from app.services import notifications as notifications_service
from app.services import rewards as rewards_service
from app.services.orders import order_out
from app.services.settings import get_store_settings

logger = get_logger(__name__)

# Where an order may go next. Cancelling is only possible before dispatch, which
# is what the customer app promises; after that the shop handles it by phone.
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    # Keep the original direct-to-shipped action for orders created before the
    # merchant workflow rollout; current UI follows accepted → packing.
    OrderStatus.processing: frozenset(
        {OrderStatus.accepted, OrderStatus.shipped, OrderStatus.cancelled}
    ),
    OrderStatus.accepted: frozenset({OrderStatus.packing, OrderStatus.cancelled}),
    OrderStatus.packing: frozenset({OrderStatus.shipped, OrderStatus.cancelled}),
    OrderStatus.shipped: frozenset({OrderStatus.out_for_delivery}),
    OrderStatus.out_for_delivery: frozenset({OrderStatus.delivered}),
    OrderStatus.delivered: frozenset({OrderStatus.returned}),
    OrderStatus.cancelled: frozenset(),
    OrderStatus.returned: frozenset(),
}

#: A delivery promise only means something while the goods are still ours.
FINISHED_STATUSES = frozenset({OrderStatus.delivered, OrderStatus.cancelled, OrderStatus.returned})

#: Orders in these states still need the shop to do something.
OPEN_STATUSES = frozenset(
    {
        OrderStatus.processing,
        OrderStatus.accepted,
        OrderStatus.packing,
        OrderStatus.shipped,
        OrderStatus.out_for_delivery,
    }
)


def summary_out(order: Order) -> AdminOrderSummaryOut:
    first = order.items[0] if order.items else None
    return AdminOrderSummaryOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        payment_status=order.payment_status.value,
        wallet_paise=order.wallet_paise,
        total_paise=order.total_paise,
        item_count=order.item_count,
        placed_at=order.placed_at,
        deliver_by=order.deliver_by,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        first_item_name=first.name if first else "",
        first_item_image_url=first.image_url if first else "",
        assigned_to=order.assigned_to,
        assigned_driver_name=order.delivery_profile.name if order.delivery_profile else "",
        is_new=order.status is OrderStatus.processing,
    )


async def list_orders(
    session: AsyncSession,
    *,
    status: str | None,
    search: str | None,
    order_date: date | None,
    payment_status: str | None,
    page: int,
    page_size: int,
) -> AdminOrderListOut:
    total = await repo.count_all_orders(
        session,
        status=status,
        search=search,
        order_date=order_date,
        payment_status=payment_status,
    )
    rows = await repo.list_all_orders(
        session,
        status=status,
        search=search,
        order_date=order_date,
        payment_status=payment_status,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return AdminOrderListOut(
        items=[summary_out(order) for order in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
        counts=await repo.count_orders_by_status(session),
    )


async def get_order(session: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await repo.get_order_any(session, order_id)
    if order is None:
        raise NotFoundError("No order with that id.", code="order_not_found")
    return order


async def lock_order(session: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await repo.lock_order_any(session, order_id)
    if order is None:
        raise NotFoundError("No order with that id.", code="order_not_found")
    return order


async def transition(
    session: AsyncSession,
    order: Order,
    payload: AdminOrderStatusIn,
    *,
    actor: Profile,
) -> Order:
    target = OrderStatus(payload.status)
    allowed = ALLOWED_TRANSITIONS[order.status]
    if target not in allowed:
        raise ConflictError(
            f"This order is {order.status.value.replace('_', ' ')}, so it cannot be marked "
            f"{target.value.replace('_', ' ')}.",
            code="invalid_status_transition",
            details={
                "status": order.status.value,
                "requested": target.value,
                "allowed": sorted(status.value for status in allowed),
            },
        )

    if target is OrderStatus.cancelled:
        for item in order.items:
            if item.variant_id is not None:
                await repo.restore_variant_stock(session, item.variant_id, item.quantity)
            else:
                await repo.restore_product_stock(session, item.product_id, item.quantity)
        order.cancelled_at = datetime.now(tz=UTC)
        order.cancelled_reason = payload.note or f"Cancelled by {actor.email}"

    if target is OrderStatus.shipped and order.assigned_to is None:
        settings = await get_store_settings(session)
        default_driver_id = settings.default_delivery_profile_id
        if default_driver_id is not None:
            default_driver = await session.get(Profile, default_driver_id)
            if default_driver is not None and default_driver.role is UserRole.delivery:
                order.assigned_to = default_driver.id
                order.delivery_profile = default_driver

    now = datetime.now(tz=UTC)
    if target is OrderStatus.out_for_delivery:
        order.out_for_delivery_at = now
    if target is OrderStatus.delivered:
        # Cash on delivery: the money arrives with the goods.
        order.payment_status = PaymentStatus.paid
        order.delivered_at = now

    order.status = target
    event_actor = "delivery" if actor.role is UserRole.delivery else "admin"
    await repo.add_event(
        session,
        order.id,
        status=target.value,
        actor=event_actor,
        note=payload.note or f"Marked {target.value.replace('_', ' ')} by the store",
    )

    # Tell the customer, in the same transaction that moved the order.
    customer = await session.get(Profile, order.profile_id)
    settings = await get_store_settings(session)
    if customer is not None:
        await notifications_service.announce_status_change(
            session, order, customer, settings, note=payload.note
        )
    if customer is not None and target is OrderStatus.delivered:
        # Spend, badge, scratch card and the friend's referral reward all follow
        # delivery, in this same transaction.
        await rewards_service.on_order_delivered(session, order, customer, settings)
    elif customer is not None and target is OrderStatus.returned:
        # A return booked straight from the queue still has to give the money back.
        await rewards_service.on_order_reversed(
            session,
            order,
            customer,
            settings,
            reason="Order was returned",
            spend_paise=order.total_paise,
        )
    elif customer is not None and target is OrderStatus.cancelled:
        await rewards_service.on_order_reversed(
            session, order, customer, settings, reason="Order was cancelled"
        )

    await session.commit()
    await session.refresh(order)
    email_service.schedule_flush()
    logger.info(
        "order_status_changed",
        order_id=str(order.id),
        order_number=order.order_number,
        status=target.value,
        actor=str(actor.id),
    )
    return order


async def set_delivery_days(
    session: AsyncSession,
    order: Order,
    payload: AdminOrderDeliveryIn,
    *,
    actor: Profile,
) -> Order:
    """Change the date this one order is promised for.

    The date is counted from **today**, not from when the order was placed: the shop
    is making a new promise now, and "3 days from an order placed last week" would
    read as a date in the past. Only the promise moves — money, stock and status do
    not.
    """
    if order.status in FINISHED_STATUSES:
        raise ConflictError(
            f"This order is {order.status.value.replace('_', ' ')}, so its delivery date "
            "cannot be changed.",
            code="order_not_editable",
            details={"status": order.status.value},
        )

    promised = datetime.now(tz=UTC).date() + timedelta(days=payload.days)
    order.delivery_days = payload.days
    order.deliver_by = promised
    await repo.add_event(
        session,
        order.id,
        status=order.status.value,
        actor="admin",
        note=payload.note or f"Delivery promised by {promised:%d %b} ({payload.days}d)",
    )

    customer = await session.get(Profile, order.profile_id)
    if customer is not None:
        settings = await get_store_settings(session)
        await notifications_service.announce_delivery_change(session, order, customer, settings)

    await session.commit()
    await session.refresh(order)
    email_service.schedule_flush()
    logger.info(
        "order_delivery_days_changed",
        order_id=str(order.id),
        order_number=order.order_number,
        days=payload.days,
        deliver_by=promised.isoformat(),
        actor=str(actor.id),
    )
    return order


def detail_out(order: Order) -> OrderOut:
    return order_out(order)
