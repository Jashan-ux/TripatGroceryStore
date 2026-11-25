"""The Rewards hub: one summary, and the four things delivery sets in motion.

When an order is marked delivered, four unrelated-looking things happen — the
customer's spend goes up, a badge may change, a scratch card unlocks, and the
friend who referred them gets paid. They are all consequences of the same fact, so
they live in one function that runs inside the admin's transaction: either the
order is delivered and all of it happened, or none of it did.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.catalogue import Profile, StoreSettings
from app.models.orders import Order
from app.schemas.rewards import RewardsSummaryOut, TierOut
from app.services import loyalty, notifications, referrals, scratch_cards, wallet

logger = get_logger(__name__)


def tier_out(profile: Profile, settings: StoreSettings) -> TierOut:
    current = profile.loyalty_tier
    spend = profile.lifetime_spend_paise
    index = loyalty.rank(current)
    next_tier = loyalty.TIER_ORDER[index + 1] if index + 1 < len(loyalty.TIER_ORDER) else None
    target = loyalty.threshold_paise(next_tier, settings) if next_tier else None
    floor = loyalty.threshold_paise(current, settings) or 0
    if target is None:
        progress = 100
        remaining = 0
    else:
        span = max(1, target - floor)
        progress = max(0, min(100, int((spend - floor) * 100 / span)))
        remaining = max(0, target - spend)
    return TierOut(
        tier=current.value,
        spend_paise=spend,
        next_tier=next_tier.value if next_tier else None,
        next_tier_at_paise=target,
        remaining_paise=remaining,
        progress_pct=progress,
    )


async def summary(
    session: AsyncSession, profile: Profile, settings: StoreSettings
) -> RewardsSummaryOut:
    return RewardsSummaryOut(
        wallet=await wallet.statement(session, profile, page=1, page_size=10),
        referrals=await referrals.program(session, profile, settings),
        scratch=await scratch_cards.list_cards(session, profile),
        tier=tier_out(profile, settings),
    )


async def on_order_delivered(
    session: AsyncSession,
    order: Order,
    profile: Profile,
    settings: StoreSettings,
    *,
    announce: bool = True,
) -> None:
    """Delivered: spend, badge, card and referral — all in the caller's transaction."""
    earned = loyalty.apply_spend(profile, order.total_paise, settings)
    if earned is not None and announce:
        await notifications.announce_tier_upgrade(
            session,
            profile,
            tier_label=loyalty.TIER_LABEL[earned],
            spend_paise=profile.lifetime_spend_paise,
            settings=settings,
        )

    card = await scratch_cards.unlock_for_order(session, order, settings)
    if card is not None and announce:
        await notifications.announce_scratch_ready(
            session, profile, card_id=card.id, order_number=order.order_number
        )

    referral = await referrals.credit_referrer_on_delivery(session, order)
    if referral is not None and announce:
        referrer = await session.get(Profile, referral.referrer_id)
        if referrer is not None:
            await notifications.announce_referral_bonus(
                session,
                referrer,
                friend_name=(profile.name.split(" ")[0] if profile.name else "Your friend"),
                amount_paise=referral.reward_paise,
                referral_id=referral.id,
                settings=settings,
            )

    logger.info(
        "rewards_applied_on_delivery",
        order_id=str(order.id),
        spend_paise=profile.lifetime_spend_paise,
        tier=profile.loyalty_tier.value,
        card_id=str(card.id) if card else None,
        referral_credited=referral is not None,
    )


async def on_order_reversed(
    session: AsyncSession,
    order: Order,
    profile: Profile,
    settings: StoreSettings,
    *,
    reason: str,
    spend_paise: int | None = None,
) -> None:
    """Cancelled or returned before delivery: take back what delivery would have given."""
    await scratch_cards.void_for_order(session, order.id, reason)
    await referrals.void_for_order(session, order, reason)
    if spend_paise is not None:
        loyalty.apply_spend(profile, -abs(spend_paise), settings)
