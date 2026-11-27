"""Models for money the customer owns instead of owes: wallet, referrals, cards.

The one rule that shows up everywhere here: a scratch card's ``amount_paise`` is
``None`` until it has been revealed. The prize is decided when the card is created
and simply not told to the client, so no request can ask for the top prize.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

WalletReasonOut = Literal[
    "referral_bonus", "scratch_card", "return_refund", "order_payment", "adjustment"
]


class WalletEntryOut(APIModel):
    id: uuid.UUID
    delta_paise: int = Field(description="Positive for money in, negative for money out.")
    balance_after_paise: int
    reason: WalletReasonOut
    note: str = ""
    order_id: uuid.UUID | None = None
    created_at: datetime


class WalletOut(APIModel):
    balance_paise: int
    entries: list[WalletEntryOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReferralJoinIn(APIModel):
    code: str = Field(min_length=4, max_length=12, description="A friend's referral code.")


class ReferralFriendOut(APIModel):
    """A friend who used this customer's code. Deliberately thin: no email, no phone."""

    name: str = ""
    status: Literal["pending", "credited", "void"]
    reward_paise: int
    joined_at: datetime
    credited_at: datetime | None = None


class MyReferralOut(APIModel):
    """The code *this* customer was referred with, if any."""

    code: str
    status: Literal["pending", "credited", "void"]
    discount_paise: int
    referrer_name: str = ""


class ReferralProgramOut(APIModel):
    code: str = Field(description="Share this; the friend gets a discount on their first order.")
    share_url: str
    friend_discount_pct: int
    referrer_reward_paise: int
    joined: int
    credited: int
    earned_paise: int
    friends: list[ReferralFriendOut]
    my_referral: MyReferralOut | None = None


class ScratchCardOut(APIModel):
    id: uuid.UUID
    status: Literal["locked", "ready", "revealed", "used", "void"]
    threshold_paise: int
    #: ``None`` until revealed — the server knows, the client does not.
    amount_paise: int | None = None
    order_id: uuid.UUID
    order_number: str = ""
    unlocked_at: datetime | None = None
    expires_at: datetime | None = None
    revealed_at: datetime | None = None
    created_at: datetime


class ScratchCardListOut(APIModel):
    cards: list[ScratchCardOut]
    ready: int
    locked: int
    revealed: int


class ScratchRevealOut(APIModel):
    card: ScratchCardOut
    credited_paise: int
    wallet_balance_paise: int


class TierOut(APIModel):
    tier: Literal["none", "gold", "platinum", "diamond"]
    spend_paise: int = Field(description="Delivered spend, net of returns.")
    next_tier: Literal["gold", "platinum", "diamond"] | None = None
    next_tier_at_paise: int | None = None
    remaining_paise: int = 0
    progress_pct: int = Field(default=0, description="0–100 towards the next badge.")


class RewardsSummaryOut(APIModel):
    wallet: WalletOut
    referrals: ReferralProgramOut
    scratch: ScratchCardListOut
    tier: TierOut
