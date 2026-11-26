"""Analytics and customer screens: the owner's view of the shop (Phase 6).

The service decides what a "day" means, what an empty range looks like, and which
customers count as top — the repository only counts. Three choices are worth
stating because they are the difference between a dashboard that can be trusted
and one that has to be interpreted:

* **Days are Haryana days.** Ranges are inclusive dates in ``Asia/Kolkata``; the
  UI never has to know about UTC, and "today" means the same thing on the owner's
  phone as it does in the kitchen.
* **A card and its drill-down are one predicate.** ``summary()`` and
  ``orders_in_range()`` both go through ``repositories.analytics``, so the revenue
  on the card equals ``total_paise`` of the list it opens. The test suite asserts
  the equality rather than trusting the comment.
* **Empty is zero.** A range with no orders answers ``0`` and an empty list; the
  screen shows "₹0" and "no orders in these days", never an error.

Ranges are clamped rather than refused: ``from`` after ``to`` swaps, and a range
longer than a year is cut to the last year. A future end is kept as asked and
simply answers zeros — silently showing this week's takings under next week's
dates would be a lie, and the owner would believe it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories import analytics as repository
from app.schemas.admin_analytics import (
    AnalyticsOrderListOut,
    AnalyticsOrderOut,
    AnalyticsSummaryOut,
    CustomerListOut,
    CustomerOrderOut,
    CustomerProfileOut,
    CustomerRowOut,
    DateRangeOut,
    LowStockListOut,
    LowStockOut,
    ProductSalesListOut,
    ProductSalesOut,
    SeriesOut,
    SeriesPointOut,
)

#: Nobody scrolls back further than this on a phone, and it keeps the query cheap.
MAX_RANGE_DAYS = 366
#: How many customers carry the "top customer" flag.
TOP_CUSTOMER_COUNT = 3
#: Recent orders on a profile — enough to recognise someone, not the whole history.
PROFILE_ORDER_LIMIT = 20


def today_in_shop_time() -> date:
    """The shop's calendar date right now (Asia/Kolkata, no tz database needed)."""
    return (datetime.now(UTC) + timedelta(hours=5, minutes=30)).date()


def resolve_range(
    from_date: date | None, to_date: date | None, *, default_days: int = 30
) -> tuple[date, date]:
    """Apply defaults and make the range sane instead of rejecting it."""
    end = to_date or today_in_shop_time()
    start = from_date or end - timedelta(days=default_days - 1)
    if start > end:
        start, end = end, start
    # A future end is *kept*, not pulled back to today: asking about next week
    # should answer "nothing yet", not silently show this week's takings.
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        start = end - timedelta(days=MAX_RANGE_DAYS - 1)
    return start, end


def range_out(from_date: date, to_date: date) -> DateRangeOut:
    return DateRangeOut(
        from_date=from_date,
        to_date=to_date,
        days=(to_date - from_date).days + 1,
        timezone=repository.SHOP_TIMEZONE,
    )


async def summary(
    session: AsyncSession, from_date: date | None, to_date: date | None
) -> AnalyticsSummaryOut:
    start, end = resolve_range(from_date, to_date)
    data = await repository.summary(session, start, end)
    repeat, distinct = await repository.repeat_customers(session, start, end)
    new = await repository.new_customers(session, start, end)
    low_stock = await repository.low_stock_count(session)

    orders = data["orders"]
    return AnalyticsSummaryOut(
        range=range_out(start, end),
        revenue_paise=data["revenue"],
        orders=orders,
        average_order_paise=int(data["revenue"] / orders) if orders else 0,
        items_sold=data["items"],
        new_customers=new,
        repeat_customers=repeat,
        repeat_rate_percent=(repeat * 100 // distinct) if distinct else 0,
        cash_pending_paise=data["cash_pending"],
        by_status=data["by_status"],
        low_stock=low_stock,
    )


async def series(session: AsyncSession, from_date: date | None, to_date: date | None) -> SeriesOut:
    start, end = resolve_range(from_date, to_date)
    points = await repository.series(session, start, end)
    return SeriesOut(
        range=range_out(start, end),
        points=[
            SeriesPointOut(day=row["day"], orders=row["orders"], revenue_paise=row["revenue"])
            for row in points
        ],
    )


async def orders_in_range(
    session: AsyncSession,
    from_date: date | None,
    to_date: date | None,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> AnalyticsOrderListOut:
    """The rows behind the revenue and orders cards."""
    start, end = resolve_range(from_date, to_date)
    data = await repository.drill_down_orders(
        session, start, end, status=status, page=page, page_size=page_size
    )
    total = data["total"]
    return AnalyticsOrderListOut(
        items=[
            AnalyticsOrderOut(
                id=row["id"],
                order_number=row["order_number"],
                status=row["status"],
                total_paise=row["total_paise"],
                item_count=row["item_count"],
                placed_at=row["placed_at"],
                customer_name=row["customer_name"],
                customer_phone=row["customer_phone"],
                customer_id=row["profile_id"],
            )
            for row in data["rows"]
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
        total_paise=data["total_paise"],
    )


async def top_products(
    session: AsyncSession, from_date: date | None, to_date: date | None, *, limit: int = 10
) -> ProductSalesListOut:
    start, end = resolve_range(from_date, to_date)
    data = await repository.top_products(session, start, end, limit=limit)
    return ProductSalesListOut(
        range=range_out(start, end),
        items=[
            ProductSalesOut(
                product_id=row["product_id"],
                name=row["name"],
                slug=row["slug"],
                units=int(row["units"]),
                revenue_paise=int(row["revenue"]),
            )
            for row in data["rows"]
        ],
        total_revenue_paise=data["total_revenue"],
        total_units=data["total_units"],
    )


async def low_stock(session: AsyncSession) -> LowStockListOut:
    rows = await repository.low_stock(session)
    return LowStockListOut(
        items=[
            LowStockOut(
                product_id=row["id"],
                name=row["name"],
                slug=row["slug"],
                stock=row["stock"],
                threshold=row["low_stock_threshold"],
                is_active=row["is_active"],
                category=row["category"],
                # A row that cannot be tapped is a dead end; the product page owns
                # the edit dialog, so the row links straight into it.
                edit_href=f"/admin/products?edit={row['id']}",
            )
            for row in rows
        ],
        total=len(rows),
    )


def _customer_row(row: Any) -> CustomerRowOut:
    return CustomerRowOut(
        id=row["id"],
        name=row["name"],
        phone=row["phone"] or "",
        email=row["email"],
        tier=row["tier"],
        lifetime_spend_paise=row["lifetime_spend_paise"],
        orders=int(row["orders"]),
        last_order_at=row["last_order_at"],
        is_top=int(row["spend_rank"]) <= TOP_CUSTOMER_COUNT and row["lifetime_spend_paise"] > 0,
    )


async def customers(
    session: AsyncSession,
    *,
    q: str | None,
    tier: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> CustomerListOut:
    data = await repository.customers(
        session, q=q, tier=tier, sort=sort, page=page, page_size=page_size
    )
    total = data["total"]
    return CustomerListOut(
        items=[_customer_row(row) for row in data["rows"]],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
        counts=data["counts"],
    )


async def customer(session: AsyncSession, profile_id: uuid.UUID) -> CustomerProfileOut:
    row = await repository.customer_profile(session, profile_id)
    if row is None:
        raise NotFoundError("That customer does not exist.", code="customer_not_found")
    orders = await repository.customer_orders(session, profile_id, limit=PROFILE_ORDER_LIMIT)
    total = int(row["orders"])
    spend = int(row["lifetime_spend_paise"])
    return CustomerProfileOut(
        id=row["id"],
        name=row["name"],
        phone=row["phone"] or "",
        email=row["email"],
        tier=row["tier"],
        referral_code=row["referral_code"],
        lifetime_spend_paise=spend,
        orders=total,
        first_order_at=row["first_order_at"],
        last_order_at=row["last_order_at"],
        average_order_paise=(spend // total) if total else 0,
        is_top=int(row["spend_rank"]) <= TOP_CUSTOMER_COUNT and spend > 0,
        addresses=int(row["addresses"] or 0),
        recent_orders=[
            CustomerOrderOut(
                id=order["id"],
                order_number=order["order_number"],
                status=order["status"],
                total_paise=order["total_paise"],
                item_count=order["item_count"],
                placed_at=order["placed_at"],
            )
            for order in orders
        ],
    )
