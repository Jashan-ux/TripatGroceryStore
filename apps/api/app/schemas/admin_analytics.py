"""Typed responses for the owner's analytics and customer screens (Phase 6).

Two rules shape every model here.

**A card and its drill-down must be the same query.** The summary carries the
figures; the matching listing endpoint returns the rows those figures were summed
from, and its own ``total_paise`` / ``count`` are computed by the *same* predicate.
If they ever disagree, a test fails — the owner should never have to wonder
whether the number on the card is the number of orders underneath it.

**An empty range is a normal answer.** No orders is zeros and empty lists, not a
404 and not ``null``; the shop is closed on some days and the screen has to say
"₹0" rather than "error".
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.common import APIModel


class DateRangeOut(APIModel):
    """The range actually applied, after defaulting and clamping."""

    from_date: date
    to_date: date
    days: int = Field(description="Inclusive number of shop-days in the range.")
    timezone: str = Field(description="The zone a 'day' means here (Asia/Kolkata).")


class AnalyticsSummaryOut(APIModel):
    """The six numbers the owner opens the app for."""

    range: DateRangeOut
    revenue_paise: int = Field(description="Sum of order totals, excluding cancelled and returned.")
    orders: int = Field(description="Orders placed in the range, same predicate as revenue.")
    average_order_paise: int = Field(description="0 when there were no orders.")
    items_sold: int
    new_customers: int = Field(description="First order ever placed inside the range.")
    repeat_customers: int = Field(description="Customers with 2+ orders inside the range.")
    repeat_rate_percent: int = Field(description="repeat / distinct customers, rounded down.")
    cash_pending_paise: int = Field(description="Cash still to collect on undelivered orders.")
    by_status: dict[str, int] = Field(description="Order counts per status inside the range.")
    low_stock: int = Field(description="Products at or below their own threshold.")


class SeriesPointOut(APIModel):
    """One shop-day. Every day in the range appears, zero or not."""

    day: date
    orders: int
    revenue_paise: int


class SeriesOut(APIModel):
    range: DateRangeOut
    points: list[SeriesPointOut]


class AnalyticsOrderOut(APIModel):
    """A row in the drill-down behind the revenue and orders cards."""

    id: uuid.UUID
    order_number: str
    status: str
    total_paise: int
    item_count: int
    placed_at: datetime
    customer_name: str
    customer_phone: str
    customer_id: uuid.UUID


class AnalyticsOrderListOut(APIModel):
    items: list[AnalyticsOrderOut]
    page: int
    page_size: int
    total: int
    total_pages: int
    #: Sum over the *whole* filtered set, not just this page — it must equal the card.
    total_paise: int


class ProductSalesOut(APIModel):
    product_id: uuid.UUID
    name: str
    slug: str
    units: int
    revenue_paise: int


class ProductSalesListOut(APIModel):
    range: DateRangeOut
    items: list[ProductSalesOut]
    total_revenue_paise: int = Field(description="Revenue from all sold lines in the range.")
    total_units: int


class LowStockOut(APIModel):
    """One row of "running out" — it always knows where its fix lives."""

    product_id: uuid.UUID
    name: str
    slug: str
    stock: int
    threshold: int
    is_active: bool
    category: str
    edit_href: str = Field(description="Admin route that opens this product's edit dialog.")


class LowStockListOut(APIModel):
    items: list[LowStockOut]
    total: int


class CustomerRowOut(APIModel):
    id: uuid.UUID
    name: str
    phone: str
    email: str
    tier: str
    lifetime_spend_paise: int
    orders: int
    last_order_at: datetime | None
    is_top: bool = Field(description="Inside the shop's top three by lifetime spend.")


class CustomerListOut(APIModel):
    items: list[CustomerRowOut]
    page: int
    page_size: int
    total: int
    total_pages: int
    counts: dict[str, int] = Field(description="Customers per tier across the whole shop.")


class CustomerOrderOut(APIModel):
    id: uuid.UUID
    order_number: str
    status: str
    total_paise: int
    item_count: int
    placed_at: datetime


class CustomerProfileOut(APIModel):
    id: uuid.UUID
    name: str
    phone: str
    email: str
    tier: str
    referral_code: str
    lifetime_spend_paise: int
    orders: int
    first_order_at: datetime | None
    last_order_at: datetime | None
    average_order_paise: int
    is_top: bool
    addresses: int
    recent_orders: list[CustomerOrderOut] = Field(description="Newest first, capped.")
