"""Offers: compose one message, choose who hears it, and see what reached them."""

from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUserDep, SessionDep
from app.schemas.admin_ops import OfferIn, OfferListOut, OfferOut
from app.services import offers as service
from app.services.settings import get_store_settings

router = APIRouter(prefix="/admin/offers", tags=["admin"])


@router.get("", response_model=OfferListOut, summary="What the shop has sent, newest first")
async def list_offers(
    _: AdminUserDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OfferListOut:
    items, total = await service.list_page(session, page=page, page_size=page_size)
    return OfferListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "",
    response_model=OfferOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send an offer to everyone or to one loyalty tier",
)
async def send_offer(user: AdminUserDep, session: SessionDep, payload: OfferIn) -> OfferOut:
    settings = await get_store_settings(session)
    offer = await service.send(session, user.profile, payload, settings)
    await session.commit()
    return service.offer_out(offer)
