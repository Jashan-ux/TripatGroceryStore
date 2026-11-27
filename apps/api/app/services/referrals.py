"""Referrals: one friend, one code, one discount, one reward.

The brief's rules, in order:

* a friend gets **10% off their first order** (percentage from ``store_settings``);
* the referrer gets **₹20** — but only once that first order has been *delivered*,
  because an order that is cancelled or returned never happened;
* referring yourself is refused, and so is joining after you have already ordered,
  since "first order" would then be a lie.

The database holds the two guarantees: ``referrals.referee_id`` is unique (a
customer can be referred once) and ``credited_entry_id`` is unique (a reward can be
paid once).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import ReferralStatus, WalletReason
from app.models.orders import Order
from app.models.rewards import Referral
from app.repositories import orders as orders_repo
from app.repositories import profiles as profiles_repo
from app.repositories import rewards as repo
from app.schemas.rewards import MyReferralOut, ReferralFriendOut, ReferralProgramOut
from app.services import wallet as wallet_service

logger = get_logger(__name__)


def friend_discount_paise(subtotal_paise: int, settings: StoreSettings) -> int:
    """Whole rupees, floored — a discount can never round up past the percentage."""
    pct = max(0, min(100, settings.referral_friend_discount_pct))
    return (subtotal_paise * pct) // 100


def discount_reason(settings: StoreSettings) -> str:
    return f"Referral {settings.referral_friend_discount_pct}% off"


async def join(
    session: AsyncSession, profile: Profile, code: str, settings: StoreSettings
) -> Referral:
    """Attach a friend's code to this customer, once, before their first order."""
    cleaned = code.strip().upper()
    if not cleaned:
        raise ConflictError("Enter a referral code.", code="referral_code_missing")

    if await repo.get_referral_for_referee(session, profile.id) is not None:
        raise ConflictError(
            "You have already used a referral code.",
            code="referral_already_joined",
        )

    referrer = await profiles_repo.get_profile_by_referral_code(session, cleaned)
    if referrer is None:
        raise NotFoundError(
            "That code does not belong to anyone here. Check it and try again.",
            code="referral_code_not_found",
        )
    if referrer.id == profile.id:
        raise ConflictError(
            "You cannot refer yourself.", code="self_referral", details={"code": cleaned}
        )

    if await orders_repo.count_orders(session, profile.id) > 0:
        raise ConflictError(
            "Referral codes only work before your first order.", code="referral_after_first_order"
        )

    referral = Referral(
        referrer_id=referrer.id,
        referee_id=profile.id,
        code=cleaned,
        status=ReferralStatus.pending,
        reward_paise=settings.referral_referrer_reward_paise,
    )
    await repo.add_referral(session, referral)
    # The column on the profile is what the UI and the seed already read.
    profile.referred_by = referrer.id
    await session.commit()
    await session.refresh(referral)
    logger.info(
        "referral_joined",
        referral_id=str(referral.id),
        referrer_id=str(referrer.id),
        referee_id=str(profile.id),
    )
    return referral


async def discount_for_first_order(
    session: AsyncSession,
    profile: Profile,
    order_id: uuid.UUID,
    subtotal_paise: int,
    settings: StoreSettings,
) -> tuple[int, str]:
    """What this order gets off for having been referred — once, on the first one."""
    referral = await repo.get_referral_for_update(session, profile.id)
    if referral is None or referral.status is not ReferralStatus.pending:
        return 0, ""
    if referral.first_order_id is not None and referral.first_order_id != order_id:
        return 0, ""
    discount = min(friend_discount_paise(subtotal_paise, settings), subtotal_paise)
    if discount <= 0:
        return 0, ""
    referral.discount_paise = discount
    referral.first_order_id = order_id
    return discount, discount_reason(settings)


async def credit_referrer_on_delivery(session: AsyncSession, order: Order) -> Referral | None:
    """The friend's first order landed: pay the person who brought them."""
    referral = await repo.get_referral_for_update(session, order.profile_id)
    if referral is None or referral.status is not ReferralStatus.pending:
        return None
    if referral.first_order_id is not None and referral.first_order_id != order.id:
        return None

    entry = await wallet_service.credit(
        session,
        referral.referrer_id,
        referral.reward_paise,
        WalletReason.referral_bonus,
        note="A friend you referred received their first order",
        order_id=order.id,
    )
    referral.status = ReferralStatus.credited
    referral.credited_entry_id = entry.id
    referral.credited_at = datetime.now(tz=UTC)
    referral.first_order_id = order.id
    logger.info(
        "referral_credited",
        referral_id=str(referral.id),
        referrer_id=str(referral.referrer_id),
        reward_paise=referral.reward_paise,
    )
    return referral


async def void_for_order(session: AsyncSession, order: Order, reason: str) -> Referral | None:
    """The first order was called off or came back, so nothing is owed."""
    referral = await repo.get_referral_for_update(session, order.profile_id)
    if referral is None or referral.status is not ReferralStatus.pending:
        return None
    if referral.first_order_id is not None and referral.first_order_id != order.id:
        return None
    referral.status = ReferralStatus.void
    logger.info("referral_void", referral_id=str(referral.id), reason=reason)
    return referral


async def program(
    session: AsyncSession, profile: Profile, settings: StoreSettings
) -> ReferralProgramOut:
    """Everything the Rewards page needs about the two sides of a referral."""
    referrals = await repo.list_referrals(session, profile.id)
    counts = await repo.count_referrals(session, profile.id)

    friends: list[ReferralFriendOut] = []
    for referral in referrals:
        friend = await session.get(Profile, referral.referee_id)
        friends.append(
            ReferralFriendOut(
                # First name only: the referrer does not get a new contact's details.
                name=(friend.name.split(" ")[0] if friend and friend.name else "A friend"),
                status=referral.status.value,
                reward_paise=referral.reward_paise,
                joined_at=referral.created_at,
                credited_at=referral.credited_at,
            )
        )

    mine = await repo.get_referral_for_referee(session, profile.id)
    my_referral: MyReferralOut | None = None
    if mine is not None:
        referrer = await session.get(Profile, mine.referrer_id)
        my_referral = MyReferralOut(
            code=mine.code,
            status=mine.status.value,
            discount_paise=mine.discount_paise,
            referrer_name=(referrer.name.split(" ")[0] if referrer and referrer.name else ""),
        )

    return ReferralProgramOut(
        code=profile.referral_code,
        share_url=f"/sign-up?ref={profile.referral_code}",
        friend_discount_pct=settings.referral_friend_discount_pct,
        referrer_reward_paise=settings.referral_referrer_reward_paise,
        joined=counts.get("pending", 0) + counts.get("credited", 0),
        credited=counts.get("credited", 0),
        earned_paise=sum(
            referral.reward_paise
            for referral in referrals
            if referral.status is ReferralStatus.credited
        ),
        friends=friends,
        my_referral=my_referral,
    )
