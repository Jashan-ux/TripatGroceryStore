"""Profile and phone models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class ProfileOut(APIModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None = None
    role: Literal["customer", "admin", "delivery"]
    referral_code: str
    lifetime_spend_paise: int = 0
    loyalty_tier: Literal["none", "gold", "platinum", "diamond"]
    notification_prefs: dict[str, Any] = Field(default_factory=dict)
    has_phone: bool
    created_at: datetime


class ProfileUpdateIn(APIModel):
    name: str = Field(min_length=2, max_length=120, examples=["Jashan Aneja"])

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Please enter your name.")
        return cleaned


class PhoneIn(APIModel):
    # Deliberately permissive: the service validates and answers with the
    # domain error code (`invalid_phone`), so every bad number gets the same
    # answer whether it is too short, too long or not a mobile number at all.
    phone: str = Field(
        min_length=1,
        max_length=32,
        examples=["+91 87089-73386"],
        description="Indian mobile number; +91, spaces and dashes are accepted.",
    )


class NotificationPrefsIn(APIModel):
    email: bool = True
    push: bool = True
    offers: bool = True
