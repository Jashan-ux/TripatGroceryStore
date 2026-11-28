"""Catalogue queries.

All filtering, ordering and pagination happens in SQL; nothing is filtered in
Python after the fact (ownership-scoped queries live in their own repositories).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalogue import Brand, Category, Product, ProductVariant

SortKey = str

SORTS: dict[str, tuple[Any, ...]] = {
    "popular": (Product.sort_order.asc(), Product.rating.desc(), Product.name.asc()),
    "rating": (Product.rating.desc(), Product.name.asc()),
    "price_asc": (Product.price_paise.asc(), Product.name.asc()),
    "price_desc": (Product.price_paise.desc(), Product.name.asc()),
    "newest": (Product.created_at.desc(), Product.name.asc()),
    "name": (Product.name.asc(),),
}


@dataclass(frozen=True)
class ProductFilters:
    q: str | None = None
    category_slug: str | None = None
    brand_slug: str | None = None
    min_price_paise: int | None = None
    max_price_paise: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    in_stock_only: bool = False
    sort: SortKey = "popular"
    page: int = 1
    page_size: int = 20


async def list_categories(
    session: AsyncSession, *, include_inactive: bool = False
) -> list[Category]:
    stmt: Select[Any] = select(Category).order_by(Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    result = await session.scalars(stmt)
    return list(result.unique())


async def get_category_by_slug(session: AsyncSession, slug: str) -> Category | None:
    return cast(
        "Category | None", await session.scalar(select(Category).where(Category.slug == slug))
    )


async def category_descendant_ids(session: AsyncSession, category_id: uuid.UUID) -> list[uuid.UUID]:
    """The category itself plus its direct children (two levels by design)."""
    rows = await session.scalars(select(Category.id).where(Category.parent_id == category_id))
    return [category_id, *rows.all()]


async def list_brands(session: AsyncSession, *, only_with_products: bool = True) -> list[Brand]:
    stmt = select(Brand).where(Brand.is_active.is_(True)).order_by(Brand.name)
    if only_with_products:
        stmt = stmt.where(
            Brand.id.in_(select(Product.brand_id).where(Product.is_active.is_(True)).distinct())
        )
    return list(await session.scalars(stmt))


def _product_query(filters: ProductFilters, *, category_ids: list[uuid.UUID] | None) -> Select[Any]:
    stmt = select(Product).where(Product.is_active.is_(True))
    if filters.q:
        term = filters.q.strip().lower()
        if term:
            like = f"%{term}%"
            stmt = stmt.where(
                or_(
                    Product.search_text.ilike(like),
                    Product.name.ilike(like),
                )
            )
    if category_ids:
        stmt = stmt.where(Product.category_id.in_(category_ids))
    if filters.brand_slug:
        stmt = stmt.where(Product.brand.has(Brand.slug == filters.brand_slug))
    if filters.min_price_paise is not None:
        stmt = stmt.where(Product.price_paise >= filters.min_price_paise)
    if filters.max_price_paise is not None:
        stmt = stmt.where(Product.price_paise <= filters.max_price_paise)
    if filters.tags:
        stmt = stmt.where(Product.tags.overlap(list(filters.tags)))
    if filters.in_stock_only:
        # A product with variants is in stock when any active variant is.
        stmt = stmt.where(
            or_(
                and_(Product.stock > 0, ~Product.variants.any(ProductVariant.is_active.is_(True))),
                Product.variants.any(
                    and_(ProductVariant.is_active.is_(True), ProductVariant.stock > 0)
                ),
            )
        )
    return stmt


async def list_products(
    session: AsyncSession, filters: ProductFilters, *, category_ids: list[uuid.UUID] | None = None
) -> tuple[list[Product], int]:
    base = _product_query(filters, category_ids=category_ids)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0

    order = SORTS.get(filters.sort, SORTS["popular"])
    stmt = (
        base.order_by(*order)
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
        .options(selectinload(Product.variants))
    )
    items = list((await session.scalars(stmt)).unique().all())
    return items, int(total)


async def get_product_by_slug(session: AsyncSession, slug: str) -> Product | None:
    stmt = (
        select(Product)
        .where(Product.slug == slug, Product.is_active.is_(True))
        .options(selectinload(Product.variants))
    )
    return cast("Product | None", await session.scalar(stmt))


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    stmt = select(Product).where(Product.id == product_id).options(selectinload(Product.variants))
    return cast("Product | None", await session.scalar(stmt))


async def products_for_categories(
    session: AsyncSession,
    groups: dict[uuid.UUID, list[uuid.UUID]],
    *,
    per_category: int = 8,
) -> dict[uuid.UUID, list[Product]]:
    """One rail per top-level category, in a single round trip.

    ``groups`` maps a department to itself plus its subcategories, because a
    product is filed under "Mustard Oil" while the rail is "Edible Oils & Ghee".
    """
    if not groups:
        return {}
    parent_of: dict[uuid.UUID, uuid.UUID] = {}
    for parent_id, category_ids in groups.items():
        for category_id in category_ids:
            parent_of[category_id] = parent_id

    stmt = (
        select(Product)
        .where(
            Product.category_id.in_(list(parent_of)),
            Product.is_active.is_(True),
            Product.is_featured.is_(True),
        )
        .order_by(Product.sort_order.asc(), Product.rating.desc(), Product.name)
        .options(selectinload(Product.variants))
    )
    rows = list((await session.scalars(stmt)).unique().all())
    grouped: dict[uuid.UUID, list[Product]] = {}
    for product in rows:
        parent_id = parent_of[product.category_id]
        bucket = grouped.setdefault(parent_id, [])
        if len(bucket) < per_category:
            bucket.append(product)
    return grouped
