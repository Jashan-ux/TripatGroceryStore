"""Owner onboarding of the delivery worker and assignment choices."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUserDep, SessionDep
from app.schemas.delivery import (
    DeliveryCandidateOut,
    DeliveryProfileOut,
    PromoteDeliveryProfileIn,
)
from app.services import delivery as service

router = APIRouter(prefix="/admin/delivery", tags=["admin"])


@router.get("/profiles", response_model=list[DeliveryProfileOut])
async def list_delivery_profiles(_: AdminUserDep, session: SessionDep) -> list[DeliveryProfileOut]:
    return await service.list_delivery_profiles(session)


@router.get("/candidates", response_model=list[DeliveryCandidateOut])
async def list_candidates(
    _: AdminUserDep,
    session: SessionDep,
    q: Annotated[str, Query(max_length=64)] = "",
) -> list[DeliveryCandidateOut]:
    return await service.list_candidates(session, q)


@router.post(
    "/profiles",
    response_model=DeliveryProfileOut,
    status_code=status.HTTP_200_OK,
    summary="Enable an existing customer account as a delivery profile",
)
async def promote_profile(
    user: AdminUserDep, session: SessionDep, payload: PromoteDeliveryProfileIn
) -> DeliveryProfileOut:
    return await service.promote_profile(session, payload.profile_id, actor=user.profile)
