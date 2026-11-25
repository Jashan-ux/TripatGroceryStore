"""The customer's own orders: list, detail and cancellation.

There is no ``/orders/{id}`` that any other customer can read: the query filters
by ``profile_id``, so a wrong id is a 404 with no hint that the order exists.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.orders import OrderCancelIn, OrderListOut, OrderOut
from app.services import orders as service

router = APIRouter(prefix="/orders", tags=["orders"])

OrderId = Annotated[uuid.UUID, Path(description="Order id")]


@router.get("", response_model=OrderListOut, summary="My orders")
async def list_orders(
    user: CurrentUserDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> OrderListOut:
    return await service.list_my_orders(session, user.profile, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderOut, summary="One of my orders")
async def get_order(user: CurrentUserDep, session: SessionDep, order_id: OrderId) -> OrderOut:
    order = await service.get_my_order(session, user.profile, order_id)
    return service.order_out(order)


@router.post("/{order_id}/cancel", response_model=OrderOut, summary="Cancel while processing")
async def cancel_order(
    user: CurrentUserDep,
    session: SessionDep,
    order_id: OrderId,
    payload: OrderCancelIn | None = None,
) -> OrderOut:
    reason = payload.reason if payload is not None else ""
    order = await service.cancel_order(session, user.profile, order_id, reason)
    return service.order_out(order)
