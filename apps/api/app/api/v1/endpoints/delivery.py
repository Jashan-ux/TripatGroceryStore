"""Driver-only mobile workspace. Every order lookup is scoped by assigned_to."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Path

from app.api.deps import DeliveryUserDep, SessionDep
from app.schemas.delivery import DeliveryOrderListOut, DeliveryOrderOut
from app.services import delivery as service
from app.services import notifications, push

router = APIRouter(prefix="/delivery", tags=["delivery"])
OrderId = Annotated[uuid.UUID, Path(description="Assigned delivery order id")]


@router.get("/orders", response_model=DeliveryOrderListOut, summary="My active assigned deliveries")
async def list_my_orders(user: DeliveryUserDep, session: SessionDep) -> DeliveryOrderListOut:
    return await service.list_assigned_orders(session, user.id)


async def _mark_status(
    *,
    user: DeliveryUserDep,
    session: SessionDep,
    order_id: uuid.UUID,
    delivered: bool,
    background_tasks: BackgroundTasks,
) -> DeliveryOrderOut:
    order, changed = await service.update_delivery_status(
        session, user.profile, order_id, delivered=delivered
    )
    if changed:
        headline, detail = notifications.STATUS_COPY[order.status]
        background_tasks.add_task(
            push.deliver_to_profile,
            order.profile_id,
            title=f"{order.order_number}: {headline}",
            body=detail,
            href=f"/orders/{order.id}",
        )
    return service.driver_order_out(order)


@router.post(
    "/orders/{order_id}/out-for-delivery",
    response_model=DeliveryOrderOut,
    summary="Mark an assigned order out for delivery",
)
async def mark_out_for_delivery(
    user: DeliveryUserDep,
    session: SessionDep,
    order_id: OrderId,
    background_tasks: BackgroundTasks,
) -> DeliveryOrderOut:
    return await _mark_status(
        user=user,
        session=session,
        order_id=order_id,
        delivered=False,
        background_tasks=background_tasks,
    )


@router.post(
    "/orders/{order_id}/delivered",
    response_model=DeliveryOrderOut,
    summary="Mark an assigned order delivered",
)
async def mark_delivered(
    user: DeliveryUserDep,
    session: SessionDep,
    order_id: OrderId,
    background_tasks: BackgroundTasks,
) -> DeliveryOrderOut:
    return await _mark_status(
        user=user,
        session=session,
        order_id=order_id,
        delivered=True,
        background_tasks=background_tasks,
    )
