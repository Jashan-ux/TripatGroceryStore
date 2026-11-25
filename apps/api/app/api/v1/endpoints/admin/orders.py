"""The owner's order queue.

Every route depends on ``AdminUserDep``, so the whole surface is behind one gate.
The list is filtered and paginated on the server: the shop can have thousands of
orders and the phone in the counter is not going to page through them in the
browser.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from app.api.deps import AdminUserDep, SessionDep
from app.schemas.admin_orders import (
    AdminOrderDeliveryIn,
    AdminOrderListOut,
    AdminOrderStatusIn,
    AdminOrderSummaryOut,
)
from app.schemas.orders import OrderOut
from app.services import admin_orders as service

router = APIRouter(prefix="/admin/orders", tags=["admin"])

OrderId = Annotated[uuid.UUID, Path(description="Order id")]
StatusFilter = Literal[
    "processing", "shipped", "out_for_delivery", "delivered", "cancelled", "returned"
]


@router.get("", response_model=AdminOrderListOut, summary="Every order, newest first")
async def list_orders(
    _: AdminUserDep,
    session: SessionDep,
    status: Annotated[StatusFilter | None, Query(description="Filter by status")] = None,
    q: Annotated[
        str | None, Query(max_length=64, description="Order number, name or phone")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminOrderListOut:
    return await service.list_orders(
        session, status=status, search=q, page=page, page_size=page_size
    )


@router.get("/{order_id}", response_model=OrderOut, summary="One order, in full")
async def get_order(user: AdminUserDep, session: SessionDep, order_id: OrderId) -> OrderOut:
    order = await service.get_order(session, order_id)
    return service.detail_out(order)


@router.patch(
    "/{order_id}/delivery-days",
    response_model=AdminOrderSummaryOut,
    summary="Promise this order for a different number of days",
)
async def set_delivery_days(
    user: AdminUserDep,
    session: SessionDep,
    order_id: OrderId,
    payload: AdminOrderDeliveryIn,
) -> AdminOrderSummaryOut:
    order = await service.get_order(session, order_id)
    updated = await service.set_delivery_days(session, order, payload, actor=user.profile)
    return service.summary_out(updated)


@router.post(
    "/{order_id}/status",
    response_model=AdminOrderSummaryOut,
    summary="Move an order to its next state",
)
async def set_status(
    user: AdminUserDep,
    session: SessionDep,
    order_id: OrderId,
    payload: AdminOrderStatusIn,
) -> AdminOrderSummaryOut:
    order = await service.get_order(session, order_id)
    updated = await service.transition(session, order, payload, actor=user.profile)
    return service.summary_out(updated)
