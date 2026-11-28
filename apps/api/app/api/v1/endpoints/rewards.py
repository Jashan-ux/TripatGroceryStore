"""The Rewards hub: wallet, referral code, scratch cards and the badge.

Every route depends on ``CustomerUserDep``; there is no route here that takes a
profile id, so one customer can never read or move another's money.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import CustomerUserDep, SessionDep, rate_limit_user
from app.schemas.rewards import (
    ReferralJoinIn,
    ReferralProgramOut,
    RewardsSummaryOut,
    ScratchCardListOut,
    ScratchRevealOut,
    WalletOut,
)
from app.services import referrals as referrals_service
from app.services import rewards as rewards_service
from app.services import scratch_cards as scratch_service
from app.services import wallet as wallet_service
from app.services.settings import get_store_settings

router = APIRouter(prefix="/rewards", tags=["rewards"])

CardId = Annotated[uuid.UUID, Path(description="Scratch card id")]


@router.get("", response_model=RewardsSummaryOut, summary="Wallet, referrals, cards and badge")
async def summary(user: CustomerUserDep, session: SessionDep) -> RewardsSummaryOut:
    settings = await get_store_settings(session)
    return await rewards_service.summary(session, user.profile, settings)


@router.get("/wallet", response_model=WalletOut, summary="Wallet balance and statement")
async def wallet_statement(
    user: CustomerUserDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> WalletOut:
    return await wallet_service.statement(session, user.profile, page=page, page_size=page_size)


@router.post(
    "/referral",
    response_model=ReferralProgramOut,
    summary="Use a friend's code",
    # A wrong code counts against the budget, which is the point: codes are short,
    # so the only real defence against guessing them is that guesses cost time.
    dependencies=[Depends(rate_limit_user("referral"))],
)
async def join_referral(
    user: CustomerUserDep, session: SessionDep, payload: ReferralJoinIn
) -> ReferralProgramOut:
    settings = await get_store_settings(session)
    await referrals_service.join(session, user.profile, payload.code, settings)
    return await referrals_service.program(session, user.profile, settings)


@router.get("/scratch-cards", response_model=ScratchCardListOut, summary="My scratch cards")
async def list_cards(user: CustomerUserDep, session: SessionDep) -> ScratchCardListOut:
    return await scratch_service.list_cards(session, user.profile)


@router.post(
    "/scratch-cards/{card_id}/reveal",
    response_model=ScratchRevealOut,
    summary="Rub a card off (once)",
    dependencies=[Depends(rate_limit_user("scratch"))],
)
async def reveal_card(
    user: CustomerUserDep, session: SessionDep, card_id: CardId
) -> ScratchRevealOut:
    return await scratch_service.reveal(session, user.profile, card_id)
