"""The owner editing the shop's numbers.

Two promises are kept here:

* **No redeploy.** The settings cache is cleared the moment the row changes, so
  the next checkout, quote or tier calculation sees the new value.
* **Every change is attributable.** Before/after are written to the audit log in
  the same transaction, so "who set the minimum order to ₹800?" has an answer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnavailableError, ValidationError
from app.models.catalogue import Profile, StoreSettings
from app.repositories import settings as repo
from app.schemas.admin_ops import SettingsOut, SettingsPatchIn
from app.services import audit
from app.services import settings as settings_service


#: Cross-field rules the database also enforces; failing here gives a readable
#: message instead of a constraint error.
def validate(row: StoreSettings) -> None:
    if row.scratch_min_paise > row.scratch_max_paise:
        raise ValidationError(
            "The smallest scratch-card prize cannot be larger than the biggest.",
            code="invalid_settings",
            details={"field": "scratch_min_paise"},
        )
    if not (row.tier_gold_paise < row.tier_platinum_paise < row.tier_diamond_paise):
        raise ValidationError(
            "Badge thresholds must grow: Gold < Platinum < Diamond.",
            code="invalid_settings",
            details={"field": "tier_gold_paise"},
        )
    if row.feedback_email and "@" not in row.feedback_email:
        raise ValidationError(
            "That feedback address does not look like an email.",
            code="invalid_settings",
            details={"field": "feedback_email"},
        )
    if row.store_maps_url and not row.store_maps_url.startswith("https://"):
        raise ValidationError(
            "The Maps link must start with https://.",
            code="invalid_settings",
            details={"field": "store_maps_url"},
        )


def settings_out(row: StoreSettings) -> SettingsOut:
    return SettingsOut(
        store_name=row.store_name,
        store_phone=row.store_phone,
        store_address=row.store_address,
        store_maps_url=row.store_maps_url,
        feedback_email=row.feedback_email,
        notification_email=row.notification_email,
        minimum_order_paise=row.minimum_order_paise,
        serviceable_pincodes=list(row.serviceable_pincodes or []),
        default_delivery_days=row.default_delivery_days,
        is_open=row.is_open,
        low_stock_threshold=row.low_stock_threshold,
        referral_referrer_reward_paise=row.referral_referrer_reward_paise,
        referral_friend_discount_pct=row.referral_friend_discount_pct,
        scratch_threshold_paise=row.scratch_threshold_paise,
        scratch_min_paise=row.scratch_min_paise,
        scratch_max_paise=row.scratch_max_paise,
        scratch_expiry_days=row.scratch_expiry_days,
        return_window_days=row.return_window_days,
        tier_gold_paise=row.tier_gold_paise,
        tier_platinum_paise=row.tier_platinum_paise,
        tier_diamond_paise=row.tier_diamond_paise,
        updated_at=row.updated_at,
    )


def _snapshot(row: StoreSettings) -> dict[str, Any]:
    return {
        "store_name": row.store_name,
        "store_phone": row.store_phone,
        "store_address": row.store_address,
        "store_maps_url": row.store_maps_url,
        "feedback_email": row.feedback_email,
        "notification_email": row.notification_email,
        "minimum_order_paise": row.minimum_order_paise,
        "serviceable_pincodes": list(row.serviceable_pincodes or []),
        "default_delivery_days": row.default_delivery_days,
        "is_open": row.is_open,
        "low_stock_threshold": row.low_stock_threshold,
        "referral_referrer_reward_paise": row.referral_referrer_reward_paise,
        "referral_friend_discount_pct": row.referral_friend_discount_pct,
        "scratch_threshold_paise": row.scratch_threshold_paise,
        "scratch_min_paise": row.scratch_min_paise,
        "scratch_max_paise": row.scratch_max_paise,
        "scratch_expiry_days": row.scratch_expiry_days,
        "return_window_days": row.return_window_days,
        "tier_gold_paise": row.tier_gold_paise,
        "tier_platinum_paise": row.tier_platinum_paise,
        "tier_diamond_paise": row.tier_diamond_paise,
    }


async def read(session: AsyncSession) -> SettingsOut:
    row = await repo.get_settings_row(session)
    if row is None:  # pragma: no cover - the baseline migration inserts it
        raise UnavailableError("The settings row is missing.", code="settings_missing")
    return settings_out(row)


async def update(session: AsyncSession, actor: Profile, payload: SettingsPatchIn) -> SettingsOut:
    row = await repo.get_settings_row(session)
    if row is None:  # pragma: no cover - the baseline migration inserts it
        raise UnavailableError("The settings row is missing.", code="settings_missing")

    before = _snapshot(row)
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is None:
            continue
        setattr(row, field, value)
    validate(row)
    await session.flush()
    # `updated_at` is maintained by the database, so the flushed row is stale
    # until it is read back. In an async session any implicit refresh raises
    # instead of quietly costing a round trip, so ask for it explicitly.
    await session.refresh(row)

    after = _snapshot(row)
    changed = audit.diff(before, after)
    await audit.record(
        session,
        actor=actor,
        action="settings.updated",
        entity="settings",
        entity_id=None,
        summary=", ".join(changed.keys()) or "no change",
        before={key: value["from"] for key, value in changed.items()},
        after={key: value["to"] for key, value in changed.items()},
    )
    # New numbers apply to the next request, not the next deploy.
    settings_service.invalidate_cache()
    return settings_out(row)


__all__ = ["read", "settings_out", "update", "validate"]
