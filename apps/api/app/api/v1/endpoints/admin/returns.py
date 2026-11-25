"""The owner's return queue: decide, then receive, and only then pay."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from app.api.deps import AdminUserDep, SessionDep
from app.schemas.returns import (
    AdminReturnDecisionIn,
    AdminReturnListOut,
    AdminReturnOut,
    AdminReturnReceiveIn,
)
from app.services import returns as service
from app.services.settings import get_store_settings

router = APIRouter(prefix="/admin/returns", tags=["admin"])

ReturnId = Annotated[uuid.UUID, Path(description="Return id")]
StatusFilter = Literal["requested", "approved", "rejected", "received_credited"]


def _out(order_return: object, order_number: str, name: str, phone: str) -> AdminReturnOut:
    base = service.return_out(order_return, order_number=order_number)  # type: ignore[arg-type]
    return AdminReturnOut(**base.model_dump(), customer_name=name, customer_phone=phone)


@router.get("", response_model=AdminReturnListOut, summary="Returns waiting or decided")
async def list_returns(
    _: AdminUserDep,
    session: SessionDep,
    status: Annotated[StatusFilter | None, Query(description="Filter by status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminReturnListOut:
    return await service.list_for_admin(session, status=status, page=page, page_size=page_size)


@router.post(
    "/{return_id}/decision",
    response_model=AdminReturnOut,
    summary="Approve or refuse a return",
)
async def decide(
    user: AdminUserDep,
    session: SessionDep,
    return_id: ReturnId,
    payload: AdminReturnDecisionIn,
) -> AdminReturnOut:
    settings = await get_store_settings(session)
    order_return = await service.decide(
        session,
        return_id,
        approve=payload.approve,
        note=payload.note,
        actor=user.profile,
        settings=settings,
    )
    return await service.detail_for_admin(session, order_return)


@router.post(
    "/{return_id}/received",
    response_model=AdminReturnOut,
    summary="Goods are back: restore stock, credit the wallet (once)",
)
async def received(
    user: AdminUserDep,
    session: SessionDep,
    return_id: ReturnId,
    payload: AdminReturnReceiveIn,
) -> AdminReturnOut:
    settings = await get_store_settings(session)
    order_return = await service.receive(
        session,
        return_id,
        note=payload.note,
        actor=user.profile,
        settings=settings,
    )
    return await service.detail_for_admin(session, order_return)
