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
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.catalogue import Profile
from app.models.enums import OrderStatus, PaymentStatus
from app.models.orders import Order
from app.repositories import orders as repo
from app.schemas.admin_orders import (
    AdminOrderListOut,
    AdminOrderStatusIn,
    AdminOrderSummaryOut,
)
from app.schemas.orders import OrderOut
from app.services.orders import order_out

logger = get_logger(__name__)

# Where an order may go next. Cancelling is only possible before dispatch, which
# is what the customer app promises; after that the shop handles it by phone.
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.processing: frozenset({OrderStatus.shipped, OrderStatus.cancelled}),
    OrderStatus.shipped: frozenset({OrderStatus.out_for_delivery}),
    OrderStatus.out_for_delivery: frozenset({OrderStatus.delivered}),
    OrderStatus.delivered: frozenset({OrderStatus.returned}),
    OrderStatus.cancelled: frozenset(),
    OrderStatus.returned: frozenset(),
}

#: Orders in these states still need the shop to do something.
OPEN_STATUSES = frozenset(
    {OrderStatus.processing, OrderStatus.shipped, OrderStatus.out_for_delivery}
)


def summary_out(order: Order) -> AdminOrderSummaryOut:
    first = order.items[0] if order.items else None
    return AdminOrderSummaryOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        payment_status=order.payment_status.value,
        total_paise=order.total_paise,
        item_count=order.item_count,
        placed_at=order.placed_at,
        deliver_by=order.deliver_by,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        first_item_name=first.name if first else "",
        first_item_image_url=first.image_url if first else "",
        is_new=order.status is OrderStatus.processing,
    )


async def list_orders(
    session: AsyncSession,
    *,
    status: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> AdminOrderListOut:
    total = await repo.count_all_orders(session, status=status, search=search)
    rows = await repo.list_all_orders(
        session,
        status=status,
        search=search,
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

    if target is OrderStatus.delivered:
        # Cash on delivery: the money arrives with the goods.
        order.payment_status = PaymentStatus.paid

    order.status = target
    await repo.add_event(
        session,
        order.id,
        status=target.value,
        actor="admin",
        note=payload.note or f"Marked {target.value.replace('_', ' ')} by the store",
    )
    await session.commit()
    await session.refresh(order)
    logger.info(
        "order_status_changed",
        order_id=str(order.id),
        order_number=order.order_number,
        status=target.value,
        actor=str(actor.id),
    )
    return order


def detail_out(order: Order) -> OrderOut:
    return order_out(order)
