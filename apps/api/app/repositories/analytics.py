"""SQL for analytics and customer screens (Phase 6).

Everything here reads, nothing writes. Two conventions matter more than the rest:

* **A day means a shop-day.** The shop keeps Haryana time, so a day is
  ``created_at AT TIME ZONE 'Asia/Kolkata'`` before it is truncated. An order
  placed at 23:40 IST belongs to that evening's turnover, not to the next UTC
  morning — a distinction that only shows up on the owner's phone at night, which
  is exactly when a wrong number is noticed.
* **One predicate per number.** The summary, the series and the drill-down share
  ``_revenue_predicate`` so the card and the rows it opens cannot drift apart.

Zero-filled series come from ``generate_series`` in SQL rather than from Python
loops: it keeps the "every day appears" promise in one place and avoids a second
round trip for a range with no orders in it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Order statuses that count as turnover. A cancelled order is not income, and a
#: returned one was refunded through the wallet.
REVENUE_STATUSES = ("processing", "shipped", "out_for_delivery", "delivered")

SHOP_TIMEZONE = "Asia/Kolkata"


def _revenue_predicate(alias: str = "o") -> str:
    """The single definition of "this order counts", reused everywhere."""
    return f"{alias}.status = ANY(:revenue_statuses)"


def _range_predicate(alias: str = "o") -> str:
    """Placed inside the shop-day range: [from 00:00, to+1 00:00) in shop time."""
    shop_placed = f"timezone('{SHOP_TIMEZONE}', {alias}.placed_at)"
    return f"{shop_placed} >= :from_ts AND {shop_placed} < :to_ts"


def params_for(from_date: date, to_date: date) -> dict[str, Any]:
    """Half-open bounds in shop time: [from 00:00, to+1 00:00)."""
    return {
        "from_ts": datetime.combine(from_date, time.min),
        "to_ts": datetime.combine(to_date + timedelta(days=1), time.min),
        "revenue_statuses": list(REVENUE_STATUSES),
    }


async def summary(session: AsyncSession, from_date: date, to_date: date) -> dict[str, Any]:
    row = (
        (
            await session.execute(
                text(
                    f"""
                SELECT
                  COALESCE(SUM(o.total_paise) FILTER (WHERE {_revenue_predicate()}), 0) AS revenue,
                  COUNT(*) FILTER (WHERE {_revenue_predicate()}) AS orders,
                  COALESCE(SUM(o.item_count) FILTER (WHERE {_revenue_predicate()}), 0) AS items,
                  COALESCE(SUM(o.total_paise) FILTER (
                      WHERE o.status IN ('processing', 'shipped', 'out_for_delivery')
                  ), 0) AS cash_pending
                FROM orders o
                WHERE {_range_predicate()}
                """
                ),
                params_for(from_date, to_date),
            )
        )
        .mappings()
        .one()
    )

    status_counts = (
        await session.execute(
            text(
                f"""
                SELECT o.status::text AS status, COUNT(*) AS n
                FROM orders o
                WHERE {_range_predicate()}
                GROUP BY 1
                """
            ),
            params_for(from_date, to_date),
        )
    ).all()
    return {
        "revenue": int(row["revenue"]),
        "orders": int(row["orders"]),
        "items": int(row["items"]),
        "cash_pending": int(row["cash_pending"]),
        "by_status": {status: int(count) for status, count in status_counts},
    }


async def repeat_customers(
    session: AsyncSession, from_date: date, to_date: date
) -> tuple[int, int]:
    """(repeat, distinct) — customers with 2+ counting orders inside the range."""
    row = (
        (
            await session.execute(
                text(
                    f"""
                SELECT
                  COUNT(*) FILTER (WHERE per_customer.orders >= 2) AS repeat_customers,
                  COUNT(*) AS distinct_customers
                FROM (
                  SELECT o.profile_id, COUNT(*) AS orders
                  FROM orders o
                  WHERE {_range_predicate()} AND {_revenue_predicate()}
                  GROUP BY o.profile_id
                ) per_customer
                """
                ),
                params_for(from_date, to_date),
            )
        )
        .mappings()
        .one()
    )
    return int(row["repeat_customers"]), int(row["distinct_customers"])


async def new_customers(session: AsyncSession, from_date: date, to_date: date) -> int:
    """People whose *first ever* order falls inside the range."""
    return int(
        await session.scalar(
            text(
                f"""
                SELECT COUNT(*)
                FROM (
                  SELECT o.profile_id, MIN(timezone('{SHOP_TIMEZONE}', o.placed_at)) AS first_at
                  FROM orders o
                  WHERE o.status <> 'cancelled'
                  GROUP BY o.profile_id
                ) firsts
                WHERE firsts.first_at >= :from_ts AND firsts.first_at < :to_ts
                """
            ),
            params_for(from_date, to_date),
        )
        or 0
    )


async def series(session: AsyncSession, from_date: date, to_date: date) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    f"""
                WITH days AS (
                  SELECT generate_series(
                    CAST(:from_date AS date), CAST(:to_date AS date), interval '1 day'
                  )::date AS day
                )
                SELECT days.day,
                       COUNT(o.id) FILTER (WHERE {_revenue_predicate()}) AS orders,
                       COALESCE(
                         SUM(o.total_paise) FILTER (WHERE {_revenue_predicate()}), 0
                       ) AS revenue
                FROM days
                LEFT JOIN orders o
                  ON timezone('{SHOP_TIMEZONE}', o.placed_at)::date = days.day
                GROUP BY days.day
                ORDER BY days.day
                """
                ),
                {**params_for(from_date, to_date), "from_date": from_date, "to_date": to_date},
            )
        )
        .mappings()
        .all()
    )
    return [
        {"day": row["day"], "orders": int(row["orders"]), "revenue": int(row["revenue"])}
        for row in rows
    ]


def _drill_down_where(status: str | None) -> tuple[str, dict[str, Any]]:
    """The listing's filter — identical to the card's, plus an optional status."""
    clause = f"{_range_predicate()} AND {_revenue_predicate()}"
    extra: dict[str, Any] = {}
    if status:
        clause += " AND o.status::text = :status"
        extra["status"] = status
    return clause, extra


async def drill_down_orders(
    session: AsyncSession,
    from_date: date,
    to_date: date,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    where, extra = _drill_down_where(status)
    params = {**params_for(from_date, to_date), **extra}

    totals = (
        (
            await session.execute(
                text(
                    f"""
                SELECT COUNT(*) AS total, COALESCE(SUM(o.total_paise), 0) AS total_paise
                FROM orders o WHERE {where}
                """
                ),
                params,
            )
        )
        .mappings()
        .one()
    )

    rows = (
        (
            await session.execute(
                text(
                    f"""
                SELECT o.id, o.order_number, o.status::text AS status, o.total_paise,
                       o.item_count, o.placed_at, o.customer_name, o.customer_phone, o.profile_id
                FROM orders o
                WHERE {where}
                ORDER BY o.placed_at DESC, o.order_number DESC
                LIMIT :limit OFFSET :offset
                """
                ),
                {**params, "limit": page_size, "offset": (page - 1) * page_size},
            )
        )
        .mappings()
        .all()
    )
    return {"total": int(totals["total"]), "total_paise": int(totals["total_paise"]), "rows": rows}


async def top_products(
    session: AsyncSession, from_date: date, to_date: date, *, limit: int
) -> dict[str, Any]:
    params = params_for(from_date, to_date)
    rows = (
        (
            await session.execute(
                text(
                    f"""
                SELECT p.id AS product_id, p.name, p.slug,
                       SUM(i.quantity) AS units,
                       SUM(i.line_total_paise) AS revenue
                FROM order_items i
                JOIN orders o ON o.id = i.order_id
                JOIN products p ON p.id = i.product_id
                WHERE {_range_predicate()} AND {_revenue_predicate()}
                GROUP BY p.id, p.name, p.slug
                ORDER BY revenue DESC, units DESC, p.name ASC
                LIMIT :limit
                """
                ),
                {**params, "limit": limit},
            )
        )
        .mappings()
        .all()
    )

    overall = (
        (
            await session.execute(
                text(
                    f"""
                SELECT COALESCE(SUM(i.line_total_paise), 0) AS revenue,
                       COALESCE(SUM(i.quantity), 0) AS units
                FROM order_items i
                JOIN orders o ON o.id = i.order_id
                WHERE {_range_predicate()} AND {_revenue_predicate()}
                """
                ),
                params,
            )
        )
        .mappings()
        .one()
    )
    return {
        "rows": rows,
        "total_revenue": int(overall["revenue"]),
        "total_units": int(overall["units"]),
    }


async def low_stock(session: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
    """Active products at or below their own threshold, emptiest first."""
    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT p.id, p.name, p.slug, p.stock, p.low_stock_threshold, p.is_active,
                       COALESCE(c.name, '') AS category
                FROM products p
                LEFT JOIN categories c ON c.id = p.category_id
                WHERE p.is_active AND p.stock <= p.low_stock_threshold
                ORDER BY (p.stock = 0) DESC, p.stock ASC, p.name ASC
                LIMIT :limit
                """
                ),
                {"limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def low_stock_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            text("SELECT COUNT(*) FROM products WHERE is_active AND stock <= low_stock_threshold")
        )
        or 0
    )


async def customers(
    session: AsyncSession,
    *,
    q: str | None,
    tier: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    filters = ["p.role::text = 'customer'"]
    params: dict[str, Any] = {}
    if q:
        filters.append("(p.name ILIKE :q OR p.phone ILIKE :q OR p.email ILIKE :q)")
        params["q"] = f"%{q}%"
    if tier:
        filters.append("p.loyalty_tier::text = :tier")
        params["tier"] = tier
    where = " AND ".join(filters)

    order_by = {
        "spend": "p.lifetime_spend_paise DESC, p.created_at ASC",
        "recent": "last_order_at DESC NULLS LAST, p.created_at DESC",
        "newest": "p.created_at DESC",
    }[sort]

    total = int(
        await session.scalar(text(f"SELECT COUNT(*) FROM profiles p WHERE {where}"), params) or 0
    )
    rows = (
        (
            await session.execute(
                text(
                    f"""
                SELECT p.id, p.name, p.phone, p.email, p.loyalty_tier::text AS tier,
                       p.lifetime_spend_paise,
                       COALESCE(o.orders, 0) AS orders,
                       o.last_order_at,
                       (SELECT COUNT(*) + 1 FROM profiles top_customer
                        WHERE top_customer.role::text = 'customer'
                          AND top_customer.lifetime_spend_paise > p.lifetime_spend_paise
                       ) AS spend_rank
                FROM profiles p
                LEFT JOIN (
                  SELECT profile_id, COUNT(*) AS orders, MAX(placed_at) AS last_order_at
                  FROM orders WHERE status <> 'cancelled'
                  GROUP BY profile_id
                ) o ON o.profile_id = p.id
                WHERE {where}
                ORDER BY {order_by}
                LIMIT :limit OFFSET :offset
                """
                ),
                {**params, "limit": page_size, "offset": (page - 1) * page_size},
            )
        )
        .mappings()
        .all()
    )

    counts = (
        await session.execute(
            text("""
                SELECT loyalty_tier::text AS tier, COUNT(*) AS n
                FROM profiles WHERE role::text = 'customer' GROUP BY 1
                """)
        )
    ).all()
    return {
        "rows": rows,
        "total": total,
        "counts": {row.tier: int(row.n) for row in counts},
    }


async def customer_profile(session: AsyncSession, profile_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT p.id, p.name, p.phone, p.email, p.loyalty_tier::text AS tier,
                       p.referral_code, p.lifetime_spend_paise,
                       COALESCE(o.orders, 0) AS orders,
                       o.first_order_at, o.last_order_at,
                       (SELECT COUNT(*) + 1 FROM profiles top_customer
                        WHERE top_customer.role::text = 'customer'
                          AND top_customer.lifetime_spend_paise > p.lifetime_spend_paise
                       ) AS spend_rank,
                       (SELECT COUNT(*) FROM addresses a WHERE a.profile_id = p.id) AS addresses
                FROM profiles p
                LEFT JOIN (
                  SELECT profile_id, COUNT(*) AS orders,
                         MIN(placed_at) AS first_order_at, MAX(placed_at) AS last_order_at
                  FROM orders WHERE status <> 'cancelled'
                  GROUP BY profile_id
                ) o ON o.profile_id = p.id
                WHERE p.id = :id AND p.role::text = 'customer'
                """
                ),
                {"id": profile_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def customer_orders(
    session: AsyncSession, profile_id: uuid.UUID, *, limit: int = 20
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT id, order_number, status::text AS status, total_paise, item_count, placed_at
                FROM orders
                WHERE profile_id = :id
                ORDER BY placed_at DESC
                LIMIT :limit
                """
                ),
                {"id": profile_id, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
