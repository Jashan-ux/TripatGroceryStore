"""SQL for the owner's tools: catalogue editing, offers, feedback and the audit log.

The service layer decides *what* may happen; this module only knows how to fetch
and count. Every listing here takes an explicit page so no admin screen can
accidentally pull the whole table onto a phone.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin import AuditLog, Feedback, Offer
from app.models.catalogue import Brand, Category, Product, ProductVariant
from app.models.enums import FeedbackStatus, UserRole


async def get_product_admin(
    session: AsyncSession, product_id: uuid.UUID, *, for_update: bool = False
) -> Product | None:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.category),
            selectinload(Product.brand),
        )
        .where(Product.id == product_id)
    )
    if for_update:
        stmt = stmt.with_for_update(of=Product)
    return cast(Product | None, await session.scalar(stmt))


async def lock_product_variant(
    session: AsyncSession, product_id: uuid.UUID, variant_id: uuid.UUID
) -> ProductVariant | None:
    stmt = (
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id, ProductVariant.id == variant_id)
        .with_for_update()
    )
    return cast(ProductVariant | None, await session.scalar(stmt))


async def product_slug_exists(
    session: AsyncSession, slug: str, *, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(Product.id).where(Product.slug == slug)
    if exclude is not None:
        stmt = stmt.where(Product.id != exclude)
    return await session.scalar(stmt) is not None


async def list_products_admin(
    session: AsyncSession,
    *,
    q: str | None,
    category_id: uuid.UUID | None,
    brand_id: uuid.UUID | None,
    only_inactive: bool,
    low_stock: bool,
    out_of_stock: bool,
    page: int,
    page_size: int,
) -> tuple[list[Product], int]:
    active_variant_stock = (
        select(func.sum(ProductVariant.stock))
        .where(ProductVariant.product_id == Product.id, ProductVariant.is_active.is_(True))
        .correlate(Product)
        .scalar_subquery()
    )
    available_stock = func.coalesce(active_variant_stock, Product.stock)
    stmt: Select[tuple[Product]] = select(Product).options(
        selectinload(Product.variants),
        selectinload(Product.category),
        selectinload(Product.brand),
    )
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(needle), Product.slug.ilike(needle)))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id is not None:
        stmt = stmt.where(Product.brand_id == brand_id)
    if only_inactive:
        stmt = stmt.where(Product.is_active.is_(False))
    if low_stock:
        stmt = stmt.where(available_stock <= Product.low_stock_threshold)
    if out_of_stock:
        stmt = stmt.where(available_stock <= 0)

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = await session.scalars(
        stmt.order_by(Product.name.asc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows), int(total or 0)


AsyncDBResult = tuple[list[Product], int]


async def order_lines_for_product(session: AsyncSession, product_id: uuid.UUID) -> int:
    """How many order lines point at this product. Non-zero means "do not delete"."""
    from app.models.orders import OrderItem

    return int(
        await session.scalar(
            select(func.count()).select_from(OrderItem).where(OrderItem.product_id == product_id)
        )
        or 0
    )


async def get_category(session: AsyncSession, category_id: uuid.UUID) -> Category | None:
    return cast(Category | None, await session.get(Category, category_id))


async def get_category_by_slug(session: AsyncSession, slug: str) -> Category | None:
    return cast(
        Category | None, await session.scalar(select(Category).where(Category.slug == slug))
    )


async def list_categories_admin(session: AsyncSession) -> list[Category]:
    rows = await session.scalars(select(Category).order_by(Category.sort_order, Category.name))
    return list(rows)


async def category_product_count(session: AsyncSession, category_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Product).where(Product.category_id == category_id)
        )
        or 0
    )


async def category_child_count(session: AsyncSession, category_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Category).where(Category.parent_id == category_id)
        )
        or 0
    )


async def product_counts_by_category(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(Product.category_id, func.count()).group_by(Product.category_id)
    )
    return {category_id: int(count) for category_id, count in rows}


async def child_counts_by_category(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(Category.parent_id, func.count())
        .where(Category.parent_id.is_not(None))
        .group_by(Category.parent_id)
    )
    return {parent_id: int(count) for parent_id, count in rows}


async def get_brand(session: AsyncSession, brand_id: uuid.UUID) -> Brand | None:
    return await session.get(Brand, brand_id)


async def brand_slug_exists(
    session: AsyncSession, slug: str, *, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(Brand.id).where(Brand.slug == slug)
    if exclude is not None:
        stmt = stmt.where(Brand.id != exclude)
    return await session.scalar(stmt) is not None


async def brand_name_exists(
    session: AsyncSession, name: str, *, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(Brand.id).where(func.lower(Brand.name) == name.strip().lower())
    if exclude is not None:
        stmt = stmt.where(Brand.id != exclude)
    return await session.scalar(stmt) is not None


async def list_brands_admin(session: AsyncSession) -> list[Brand]:
    rows = await session.scalars(select(Brand).order_by(Brand.name))
    return list(rows)


async def brand_product_count(session: AsyncSession, brand_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
        )
        or 0
    )


async def product_counts_by_brand(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(Product.brand_id, func.count())
        .where(Product.brand_id.is_not(None))
        .group_by(Product.brand_id)
    )
    return {brand_id: int(count) for brand_id, count in rows}


# --------------------------------------------------------------------------- #
# Offers
# --------------------------------------------------------------------------- #
async def list_offers(
    session: AsyncSession, *, page: int, page_size: int
) -> tuple[list[Offer], int]:
    total = int(await session.scalar(select(func.count()).select_from(Offer)) or 0)
    rows = await session.scalars(
        select(Offer).order_by(Offer.sent_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows), total


async def current_offer(session: AsyncSession, now: datetime) -> Offer | None:
    """The newest live offer: active and not past its expiry."""
    return cast(
        Offer | None,
        await session.scalar(
            select(Offer)
            .where(
                Offer.is_active.is_(True),
                or_(Offer.expires_at.is_(None), Offer.expires_at > now),
            )
            .order_by(Offer.sent_at.desc())
            .limit(1)
        ),
    )


async def audience_emails(
    session: AsyncSession, *, tier: str | None
) -> list[tuple[uuid.UUID, str, str]]:
    """``(profile_id, email, name)`` for every customer the offer should reach."""
    from app.models.catalogue import Profile

    stmt = select(Profile.id, Profile.email, Profile.name).where(Profile.role == UserRole.customer)
    if tier is not None:
        stmt = stmt.where(Profile.loyalty_tier == tier)
    rows = await session.execute(stmt.order_by(Profile.created_at))
    return [(profile_id, email or "", name or "") for profile_id, email, name in rows]


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #
async def add_feedback(session: AsyncSession, row: Feedback) -> Feedback:
    session.add(row)
    await session.flush()
    return row


async def get_feedback(session: AsyncSession, feedback_id: uuid.UUID) -> Feedback | None:
    return await session.get(Feedback, feedback_id)


async def list_feedback(
    session: AsyncSession, *, status: FeedbackStatus | None, page: int, page_size: int
) -> tuple[list[Feedback], int]:
    stmt = select(Feedback)
    if status is not None:
        stmt = stmt.where(Feedback.status == status)
    total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = await session.scalars(
        stmt.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows), total


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
async def add_audit(session: AsyncSession, row: AuditLog) -> AuditLog:
    session.add(row)
    await session.flush()
    return row


async def list_audit(
    session: AsyncSession, *, page: int, page_size: int
) -> tuple[list[AuditLog], int]:
    total = int(await session.scalar(select(func.count()).select_from(AuditLog)) or 0)
    rows = await session.scalars(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


__all__ = [
    "AsyncDBResult",
    "add_audit",
    "add_feedback",
    "admin_profiles",
    "audience_emails",
    "brand_name_exists",
    "brand_product_count",
    "brand_slug_exists",
    "category_child_count",
    "category_product_count",
    "child_counts_by_category",
    "current_offer",
    "get_brand",
    "get_category",
    "get_category_by_slug",
    "get_feedback",
    "get_product_admin",
    "list_audit",
    "list_brands_admin",
    "list_categories_admin",
    "list_feedback",
    "list_offers",
    "list_products_admin",
    "order_lines_for_product",
    "product_counts_by_brand",
    "product_counts_by_category",
    "product_slug_exists",
]


async def admin_profiles(session: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    """``(profile_id, email)`` for every owner. The bell is the shop's inbox."""
    from app.models.catalogue import Profile

    rows = await session.execute(
        select(Profile.id, Profile.email).where(Profile.role == UserRole.admin)
    )
    return [(profile_id, email or "") for profile_id, email in rows]
