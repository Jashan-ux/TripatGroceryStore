"""The owner's order queue.

Every route depends on ``AdminUserDep``, so the whole surface is behind one gate.
The list is filtered and paginated on the server: the shop can have thousands of
orders and the phone in the counter is not going to page through them in the
browser.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Path, Query

from app.api.deps import AdminUserDep, SessionDep
from app.core.errors import ValidationError
from app.models.catalogue import Profile
from app.schemas.admin_orders import (
    AdminOrderDeliveryIn,
    AdminOrderListOut,
    AdminOrderStatusIn,
    AdminOrderSummaryOut,
)
from app.schemas.orders import OrderOut
from app.services import admin_orders as service
from app.services import notifications as notifications_service
from app.services import push as push_service

router = APIRouter(prefix="/admin/orders", tags=["admin"])

OrderId = Annotated[uuid.UUID, Path(description="Order id")]
StatusFilter = Literal[
    "processing",
    "accepted",
    "packing",
    "shipped",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "returned",
]


@router.get("", response_model=AdminOrderListOut, summary="Every order, newest first")
async def list_orders(
    _: AdminUserDep,
    session: SessionDep,
    status: Annotated[StatusFilter | None, Query(description="Filter by status")] = None,
    q: Annotated[
        str | None, Query(max_length=64, description="Order number, name or phone")
    ] = None,
    date_filter: Annotated[
        str | None,
        Query(
            alias="date",
            pattern=r"^(today|\d{4}-\d{2}-\d{2})$",
            description="Shop date or today",
        ),
    ] = None,
    payment_status: Annotated[Literal["pending", "paid"] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminOrderListOut:
    if date_filter == "today":
        order_date = datetime.now(tz=ZoneInfo("Asia/Kolkata")).date()
    elif date_filter:
        try:
            order_date = date.fromisoformat(date_filter)
        except ValueError as exc:
            raise ValidationError("Choose a real calendar date.", code="invalid_date") from exc
    else:
        order_date = None
    return await service.list_orders(
        session,
        status=status,
        search=q,
        order_date=order_date,
        payment_status=payment_status,
        page=page,
        page_size=page_size,
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
    background_tasks: BackgroundTasks,
) -> AdminOrderSummaryOut:
    order = await service.get_order(session, order_id)
    updated = await service.set_delivery_days(session, order, payload, actor=user.profile)
    customer = await session.get(Profile, updated.profile_id)
    if customer is not None:
        background_tasks.add_task(
            push_service.deliver_to_profile,
            customer.id,
            title=f"{updated.order_number}: Delivery estimate updated",
            body=(
                f"The shop has updated your delivery estimate to {updated.deliver_by:%d %b %Y}."
                if updated.deliver_by
                else "The shop has updated your delivery estimate."
            ),
            href=f"/orders/{updated.id}",
        )
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
    background_tasks: BackgroundTasks,
) -> AdminOrderSummaryOut:
    order = await service.get_order(session, order_id)
    updated = await service.transition(session, order, payload, actor=user.profile)
    customer = await session.get(Profile, updated.profile_id)
    if customer is not None:
        headline, detail = notifications_service.STATUS_COPY[updated.status]
        background_tasks.add_task(
            push_service.deliver_to_profile,
            customer.id,
            title=f"{updated.order_number}: {headline}",
            body=payload.note or detail,
            href=f"/orders/{updated.id}",
        )
    return service.summary_out(updated)
