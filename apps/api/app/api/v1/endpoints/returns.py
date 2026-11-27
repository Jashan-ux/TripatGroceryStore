"""Customer side of returns: ask for one, and see what the shop said."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.returns import ReturnListOut, ReturnOut, ReturnRequestIn
from app.services import returns as service
from app.services.settings import get_store_settings

router = APIRouter(tags=["returns"])

OrderId = Annotated[uuid.UUID, Path(description="Order id")]


@router.post(
    "/orders/{order_id}/return",
    response_model=ReturnOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ask to return part of a delivered order",
)
async def request_return(
    user: CurrentUserDep,
    session: SessionDep,
    order_id: OrderId,
    payload: ReturnRequestIn,
) -> ReturnOut:
    settings = await get_store_settings(session)
    return await service.request_return(session, user.profile, order_id, payload, settings)


@router.get("/returns", response_model=ReturnListOut, summary="My returns")
async def list_returns(user: CurrentUserDep, session: SessionDep) -> ReturnListOut:
    return await service.list_mine(session, user.profile)
