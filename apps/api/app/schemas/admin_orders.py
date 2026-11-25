"""Owner-facing order models.

The admin surface can see every order, so it gets slightly more than the
customer view: who placed it, the per-status counts behind the dashboard tabs,
and an explicit status transition payload.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

AdminStatus = Literal["processing", "shipped", "out_for_delivery", "delivered", "cancelled"]


class AdminOrderSummaryOut(APIModel):
    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    wallet_paise: int = 0
    total_paise: int
    item_count: int
    placed_at: datetime
    deliver_by: date | None = None
    customer_name: str
    customer_phone: str
    first_item_name: str
    first_item_image_url: str
    is_new: bool = Field(description="Placed since the shop last opened the queue.")


class AdminOrderListOut(APIModel):
    items: list[AdminOrderSummaryOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    counts: dict[str, int] = Field(
        description="Orders per status across the whole shop, for the filter tabs."
    )


class AdminOrderDeliveryIn(APIModel):
    days: int = Field(ge=0, le=14, description="Days from today the shop promises.")
    note: str = Field(default="", max_length=300)


class AdminOrderStatusIn(APIModel):
    status: AdminStatus
    note: str = Field(default="", max_length=300)
