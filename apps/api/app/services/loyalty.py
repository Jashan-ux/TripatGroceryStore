"""Loyalty tiers: a badge that is earned by delivered spend, never by a birthday.

The tiers and their thresholds live in ``store_settings`` (gold ₹20,000, platinum
₹50,000, diamond ₹1,00,000 by default), so the owner can move a line without a
deploy. Spend is **net of returns**: a refunded order should not buy a badge.

Upgrading is worth telling the customer about. Downgrading is not — if a return
takes somebody back below a line, the badge quietly goes with it.
"""

from __future__ import annotations

from app.models.catalogue import Profile, StoreSettings
from app.models.enums import LoyaltyTier

#: Cheapest first. Comparisons use this order, never the alphabet.
TIER_ORDER: tuple[LoyaltyTier, ...] = (
    LoyaltyTier.none,
    LoyaltyTier.gold,
    LoyaltyTier.platinum,
    LoyaltyTier.diamond,
)

TIER_LABEL: dict[LoyaltyTier, str] = {
    LoyaltyTier.none: "Member",
    LoyaltyTier.gold: "Gold member",
    LoyaltyTier.platinum: "Platinum member",
    LoyaltyTier.diamond: "Diamond member",
}


def threshold_paise(tier: LoyaltyTier, settings: StoreSettings) -> int | None:
    return {
        LoyaltyTier.gold: settings.tier_gold_paise,
        LoyaltyTier.platinum: settings.tier_platinum_paise,
        LoyaltyTier.diamond: settings.tier_diamond_paise,
    }.get(tier)


def tier_for(spend_paise: int, settings: StoreSettings) -> LoyaltyTier:
    """The best tier the spend qualifies for, ignoring whatever is stored."""
    earned = LoyaltyTier.none
    for tier in TIER_ORDER[1:]:
        limit = threshold_paise(tier, settings)
        if limit is not None and spend_paise >= limit:
            earned = tier
    return earned


def rank(tier: LoyaltyTier) -> int:
    return TIER_ORDER.index(tier)


def apply_spend(profile: Profile, spend_paise: int, settings: StoreSettings) -> LoyaltyTier | None:
    """Move the stored spend/tier by ``spend_paise`` (negative for a refund).

    Returns the **new** tier when the customer has moved up, and ``None`` whenever
    nothing worth announcing happened — a small order, or a downgrade.
    """
    spend = max(0, profile.lifetime_spend_paise + spend_paise)
    profile.lifetime_spend_paise = spend
    earned = tier_for(spend, settings)
    previous = profile.loyalty_tier
    profile.loyalty_tier = earned
    return earned if rank(earned) > rank(previous) else None
