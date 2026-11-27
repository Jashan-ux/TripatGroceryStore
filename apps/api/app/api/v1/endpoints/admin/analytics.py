"""The owner's numbers, and a way to check them.

Every figure here has a listing that produced it: the revenue card opens the
orders behind it, the products breakdown opens the lines, and "running out" opens
the product's own edit dialog. That is the whole design of this router — a number
you cannot audit is a number you end up not believing.

Ranges are dates in shop time (Asia/Kolkata), inclusive, and forgiving: omit them
for the last 30 days, send them backwards and they are swapped, send a year and a
half and it is cut to a year. An empty range answers zeros.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import AdminUserDep, SessionDep
from app.models.enums import LoyaltyTier, OrderStatus
from app.schemas.admin_analytics import (
    AnalyticsOrderListOut,
    AnalyticsSummaryOut,
    CustomerListOut,
    CustomerProfileOut,
    LowStockListOut,
    ProductSalesListOut,
    SeriesOut,
)
from app.services import analytics as service

router = APIRouter(prefix="/admin", tags=["admin"])

FromDate = Annotated[
    date | None, Query(description="First shop-day, inclusive (default: 29 days ago)")
]
ToDate = Annotated[date | None, Query(description="Last shop-day, inclusive (default: today)")]
CustomerId = Annotated[uuid.UUID, Path(description="Customer id")]


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummaryOut,
    summary="Revenue, orders, average, repeat rate and cash still to collect",
)
async def analytics_summary(
    _: AdminUserDep,
    session: SessionDep,
    from_date: FromDate = None,
    to_date: ToDate = None,
) -> AnalyticsSummaryOut:
    return await service.summary(session, from_date, to_date)


@router.get(
    "/analytics/series",
    response_model=SeriesOut,
    summary="One point per shop-day, gaps included as zero",
)
async def analytics_series(
    _: AdminUserDep,
    session: SessionDep,
    from_date: FromDate = None,
    to_date: ToDate = None,
) -> SeriesOut:
    return await service.series(session, from_date, to_date)


@router.get(
    "/analytics/orders",
    response_model=AnalyticsOrderListOut,
    summary="The orders behind the revenue card",
)
async def analytics_orders(
    _: AdminUserDep,
    session: SessionDep,
    from_date: FromDate = None,
    to_date: ToDate = None,
    status: Annotated[OrderStatus | None, Query(description="Narrow to one status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AnalyticsOrderListOut:
    return await service.orders_in_range(
        session,
        from_date,
        to_date,
        status=status.value if status else None,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/analytics/products",
    response_model=ProductSalesListOut,
    summary="What actually sold in the range",
)
async def analytics_products(
    _: AdminUserDep,
    session: SessionDep,
    from_date: FromDate = None,
    to_date: ToDate = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ProductSalesListOut:
    return await service.top_products(session, from_date, to_date, limit=limit)


@router.get(
    "/analytics/low-stock",
    response_model=LowStockListOut,
    summary="Products at or below their own threshold, with where to fix them",
)
async def analytics_low_stock(_: AdminUserDep, session: SessionDep) -> LowStockListOut:
    return await service.low_stock(session)


@router.get(
    "/customers",
    response_model=CustomerListOut,
    summary="Who shops here: spend, tier, last order",
)
async def list_customers(
    _: AdminUserDep,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=120, description="Name, phone or email")] = None,
    tier: Annotated[LoyaltyTier | None, Query(description="Filter by loyalty tier")] = None,
    sort: Annotated[str, Query(pattern="^(spend|recent|newest)$")] = "spend",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CustomerListOut:
    return await service.customers(
        session,
        q=q,
        tier=tier.value if tier else None,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerProfileOut,
    summary="One customer, with every recent order",
)
async def get_customer(
    _: AdminUserDep, session: SessionDep, customer_id: CustomerId
) -> CustomerProfileOut:
    return await service.customer(session, customer_id)
