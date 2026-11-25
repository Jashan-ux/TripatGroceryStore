"""Typed Pydantic response models shared by every router.

Money is always integer paise, never float. Timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    """Base model: reject unknown keys so clients cannot smuggle extra fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)


class HealthComponent(APIModel):
    name: str
    status: Literal["ok", "degraded", "down", "not_configured"]
    latency_ms: float | None = None


class HealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    uptime_seconds: float
    components: list[HealthComponent]


class PublicConfig(APIModel):
    environment: str
    store_name: str
    store_phone: str
    store_address: str
    store_maps_url: str = ""
    feedback_email: str
    minimum_order_paise: int = 50_000
    serviceable_pincodes: list[str] = Field(default_factory=lambda: ["125104", "125201"])
    default_delivery_days: int = 1
    phone_otp_enabled: bool
    turnstile_enabled: bool
    supabase_url: str = ""
    supabase_anon_key: str = ""
    vapid_public_key: str = ""


class Pagination(APIModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class Page(APIModel, Generic[T]):
    items: list[T]
    pagination: Pagination


class ErrorDetail(APIModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(APIModel):
    error: ErrorDetail


class StatusResponse(APIModel):
    status: Literal["ok"] = "ok"
    server_time: datetime
