"""Catalogue business rules and shaping.

The service owns the public contract (what a card looks like, which rails the
home page shows); the repository owns SQL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.catalogue import Brand, Category, Product, ProductVariant
from app.repositories import catalogue as repo


def discount_percent(mrp_paise: int, price_paise: int) -> int:
    """Whole-percent discount off MRP, 0 when there is none."""
    if mrp_paise <= price_paise or mrp_paise <= 0:
        return 0
    return round((mrp_paise - price_paise) * 100 / mrp_paise)


def effective_stock(product: Product) -> int:
    """Variants carry their own stock; the product total is the sum of active ones."""
    active = [variant for variant in product.variants if variant.is_active]
    if active:
        return sum(max(variant.stock, 0) for variant in active)
    return max(product.stock, 0)


@dataclass(frozen=True)
class CategoryNode:
    category: Category
    children: tuple[Category, ...]
    product_count: int = 0


async def category_tree(session: AsyncSession) -> list[CategoryNode]:
    rows = await repo.list_categories(session)
    parents = [row for row in rows if row.parent_id is None]
    by_parent: dict[uuid.UUID, list[Category]] = {}
    for row in rows:
        if row.parent_id is not None:
            by_parent.setdefault(row.parent_id, []).append(row)
    return [
        CategoryNode(
            category=parent,
            children=tuple(
                sorted(by_parent.get(parent.id, []), key=lambda c: (c.sort_order, c.name))
            ),
        )
        for parent in parents
    ]


async def resolve_category_ids(
    session: AsyncSession, slug: str
) -> tuple[Category, list[uuid.UUID]]:
    category = await repo.get_category_by_slug(session, slug)
    if category is None or not category.is_active:
        raise NotFoundError("Category not found.", code="category_not_found")
    return category, await repo.category_descendant_ids(session, category.id)


async def search_products(
    session: AsyncSession, filters: repo.ProductFilters
) -> tuple[list[Product], int]:
    category_ids: list[uuid.UUID] | None = None
    if filters.category_slug:
        _, category_ids = await resolve_category_ids(session, filters.category_slug)
    return await repo.list_products(session, filters, category_ids=category_ids)


async def product_by_slug(session: AsyncSession, slug: str) -> Product:
    product = await repo.get_product_by_slug(session, slug)
    if product is None:
        raise NotFoundError("Product not found.", code="product_not_found")
    return product


async def home_rails(
    session: AsyncSession, *, per_category: int = 8
) -> list[tuple[Category, list[Product]]]:
    """Top-level categories that actually have products, each with a short rail."""
    nodes = await category_tree(session)
    # A department rail includes everything filed under its subcategories.
    groups = {
        node.category.id: [node.category.id, *(child.id for child in node.children)]
        for node in nodes
    }
    grouped = await repo.products_for_categories(session, groups, per_category=per_category)
    return [
        (node.category, grouped.get(node.category.id, []))
        for node in nodes
        if grouped.get(node.category.id)
    ]


async def active_brands(session: AsyncSession) -> list[Brand]:
    return await repo.list_brands(session)


def variant_payload(variant: ProductVariant) -> dict[str, object]:
    return {
        "id": variant.id,
        "label": variant.label,
        "mrp_paise": variant.mrp_paise,
        "price_paise": variant.price_paise,
        "stock": variant.stock,
        "discount_percent": discount_percent(variant.mrp_paise, variant.price_paise),
        "is_active": variant.is_active,
        "sort_order": variant.sort_order,
    }


def rating_value(value: Decimal | float | int) -> float:
    return float(value or 0)
