"""Admin operations contracts: settings, offers, the feedback inbox, the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel

Pincode = str


class SettingsOut(APIModel):
    """The whole singleton row, so the form can show every number it can change."""

    store_name: str
    store_phone: str
    store_address: str
    store_maps_url: str
    feedback_email: str
    notification_email: str
    minimum_order_paise: int
    serviceable_pincodes: list[str]
    default_delivery_days: int
    low_stock_threshold: int
    referral_referrer_reward_paise: int
    referral_friend_discount_pct: int
    scratch_threshold_paise: int
    scratch_min_paise: int
    scratch_max_paise: int
    scratch_expiry_days: int
    return_window_days: int
    tier_gold_paise: int
    tier_platinum_paise: int
    tier_diamond_paise: int
    updated_at: datetime


class SettingsPatchIn(APIModel):
    """Every field optional: the form sends only the inputs the owner touched."""

    store_name: str | None = Field(default=None, min_length=1, max_length=120)
    store_phone: str | None = Field(default=None, min_length=6, max_length=24)
    store_address: str | None = Field(default=None, min_length=5, max_length=500)
    store_maps_url: str | None = Field(default=None, max_length=500)
    feedback_email: str | None = Field(default=None, max_length=320)
    notification_email: str | None = Field(default=None, max_length=320)
    minimum_order_paise: int | None = Field(default=None, ge=0, le=10_00_00_000)
    serviceable_pincodes: list[Pincode] | None = Field(default=None, max_length=200)
    default_delivery_days: int | None = Field(default=None, ge=0, le=14)
    low_stock_threshold: int | None = Field(default=None, ge=0, le=100_000)
    referral_referrer_reward_paise: int | None = Field(default=None, ge=0, le=1_00_000)
    referral_friend_discount_pct: int | None = Field(default=None, ge=0, le=50)
    scratch_threshold_paise: int | None = Field(default=None, ge=0, le=1_00_00_000)
    scratch_min_paise: int | None = Field(default=None, ge=0, le=1_00_000)
    scratch_max_paise: int | None = Field(default=None, ge=0, le=1_00_000)
    scratch_expiry_days: int | None = Field(default=None, ge=1, le=365)
    return_window_days: int | None = Field(default=None, ge=0, le=30)
    tier_gold_paise: int | None = Field(default=None, ge=0, le=1_00_00_00_000)
    tier_platinum_paise: int | None = Field(default=None, ge=0, le=1_00_00_00_000)
    tier_diamond_paise: int | None = Field(default=None, ge=0, le=1_00_00_00_000)

    @field_validator("serviceable_pincodes")
    @classmethod
    def _six_digits(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for entry in value:
            pincode = entry.strip()
            if not pincode.isdigit() or len(pincode) != 6:
                raise ValueError(f"'{entry}' is not a 6-digit pincode")
            if pincode not in cleaned:
                cleaned.append(pincode)
        return cleaned


class OfferIn(APIModel):
    title: str = Field(min_length=3, max_length=140)
    body: str = Field(default="", max_length=1000)
    href: str = Field(default="/", max_length=300)
    audience: Literal["all", "gold", "platinum", "diamond"] = "all"
    expires_at: datetime | None = None

    @field_validator("href")
    @classmethod
    def _internal_only(cls, value: str) -> str:
        """A notification href is a link inside our own app, never anywhere else."""
        href = value.strip() or "/"
        if not href.startswith("/") or href.startswith("//"):
            raise ValueError("href must be a path inside this app, e.g. /search?q=ghee")
        return href


class OfferOut(APIModel):
    id: uuid.UUID
    title: str
    body: str
    href: str
    audience: str
    is_active: bool
    expires_at: datetime | None = None
    recipients: int
    emails_queued: int
    sent_at: datetime
    created_at: datetime


class OfferListOut(APIModel):
    items: list[OfferOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class CurrentOfferOut(APIModel):
    """What the storefront banner needs — nothing about who received it."""

    offer: OfferOut | None = None


class FeedbackIn(APIModel):
    name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=320)
    kind: Literal["general", "order", "product", "other"] = "general"
    message: str = Field(min_length=5, max_length=4000)


class FeedbackOut(APIModel):
    id: uuid.UUID
    name: str
    phone: str
    email: str
    kind: str
    message: str
    status: str
    read_at: datetime | None = None
    created_at: datetime
    #: Admin-only extras.
    customer_name: str = ""


class FeedbackListOut(APIModel):
    items: list[FeedbackOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditEntryOut(APIModel):
    id: uuid.UUID
    actor_email: str
    action: str
    entity: str
    entity_id: uuid.UUID | None = None
    summary: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    note: str
    created_at: datetime


class AuditListOut(APIModel):
    items: list[AuditEntryOut]
    total: int
    page: int
    page_size: int
    total_pages: int
