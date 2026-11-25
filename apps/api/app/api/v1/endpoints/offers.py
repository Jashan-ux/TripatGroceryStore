"""The storefront banner: the newest live offer, for anyone."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.admin_ops import CurrentOfferOut
from app.services import offers as service

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("/current", response_model=CurrentOfferOut, summary="The offer to show right now")
async def current_offer(session: SessionDep) -> CurrentOfferOut:
    offer = await service.current(session)
    return CurrentOfferOut(offer=service.offer_out(offer) if offer else None)
