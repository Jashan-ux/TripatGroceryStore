"""The owner's catalogue tools: what the shop may change, and what it may not.

The rules that matter, all enforced here rather than in the UI:

* A product is never deleted out from under history. If an order line points at
  it, deleting means *deactivating* — the storefront hides it, the past stays
  intact. A category that still holds products is refused unless the owner names
  where its contents should go.
* Slugs are derived, unique and stable: two products may share a name, but never
  a URL.
* Every change writes one audit row with the fields that moved.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.catalogue import Brand, Category, Product, ProductVariant, Profile
from app.repositories import admin_tools as repo
from app.schemas.admin_catalogue import (
    AdminVariantOut,
    BrandAdminOut,
    BrandIn,
    BrandUpdateIn,
    CategoryAdminOut,
    CategoryIn,
    CategoryUpdateIn,
    ProductAdminOut,
    ProductCreateIn,
    ProductUpdateIn,
    VariantIn,
)
from app.services import audit

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """A URL-safe slug. Devanagari and emoji fall away; the name is the source."""
    normalised = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = _SLUG_STRIP.sub("-", normalised.lower()).strip("-")
    return slug[:200] or "item"


async def _unique_product_slug(
    session: AsyncSession, base: str, *, exclude: uuid.UUID | None = None
) -> str:
    candidate, counter = base, 1
    while await repo.product_slug_exists(session, candidate, exclude=exclude):
        counter += 1
        candidate = f"{base[:190]}-{counter}"
    return candidate


async def _unique_brand_slug(
    session: AsyncSession, base: str, *, exclude: uuid.UUID | None = None
) -> str:
    candidate, counter = base, 1
    while await repo.brand_slug_exists(session, candidate, exclude=exclude):
        counter += 1
        candidate = f"{base[:130]}-{counter}"
    return candidate


async def _unique_category_slug(
    session: AsyncSession, base: str, *, exclude: uuid.UUID | None = None
) -> str:
    candidate, counter = base, 1
    while True:
        existing = await repo.get_category_by_slug(session, candidate)
        if existing is None or (exclude is not None and existing.id == exclude):
            return candidate
        counter += 1
        candidate = f"{base[:130]}-{counter}"


def _search_text(product: Product) -> str:
    """What the trigram index searches: name, brand, category, tags, description."""
    parts = [
        product.name,
        product.brand.name if product.brand else "",
        product.category.name if product.category else "",
        product.category.slug if product.category else "",
        " ".join(product.tags or []),
        product.description,
    ]
    return " ".join(part for part in parts if part).lower()[:4000]


def _check_prices(mrp_paise: int, price_paise: int) -> None:
    if mrp_paise and price_paise > mrp_paise:
        raise ValidationError(
            "The selling price cannot be higher than the MRP.",
            code="mrp_below_price",
            details={"field": "price_paise", "mrp_paise": mrp_paise, "price_paise": price_paise},
        )


def _variant_rows(variants: list[VariantIn]) -> list[ProductVariant]:
    labels = [variant.label.strip().lower() for variant in variants]
    if len(set(labels)) != len(labels):
        raise ValidationError(
            "Two variants share a label (for example '1 kg'). Labels must be unique per product.",
            code="duplicate_variant_label",
            details={"field": "variants"},
        )
    rows: list[ProductVariant] = []
    for index, variant in enumerate(variants):
        _check_prices(variant.mrp_paise, variant.price_paise)
        rows.append(
            ProductVariant(
                label=variant.label.strip(),
                mrp_paise=variant.mrp_paise,
                price_paise=variant.price_paise,
                stock=variant.stock,
                sort_order=variant.sort_order if variant.sort_order else index,
                is_active=variant.is_active,
            )
        )
    return rows


async def _require_category(session: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await repo.get_category(session, category_id)
    if category is None:
        raise NotFoundError(
            "That category does not exist.",
            code="category_not_found",
            details={"id": str(category_id)},
        )
    return category


async def _require_brand(session: AsyncSession, brand_id: uuid.UUID) -> Brand:
    brand = await repo.get_brand(session, brand_id)
    if brand is None:
        raise NotFoundError(
            "That brand does not exist.", code="brand_not_found", details={"id": str(brand_id)}
        )
    return brand


def snapshot(product: Product) -> dict[str, object]:
    """The fields a diff is worth taking over."""
    return {
        "name": product.name,
        "slug": product.slug,
        "category_id": str(product.category_id),
        "brand_id": str(product.brand_id) if product.brand_id else None,
        "price_paise": product.price_paise,
        "mrp_paise": product.mrp_paise,
        "stock": product.stock,
        "unit_label": product.unit_label,
        "description": product.description,
        "is_active": product.is_active,
        "images": list(product.images or []),
        "tags": list(product.tags or []),
        "variants": [
            {
                "label": variant.label,
                "price_paise": variant.price_paise,
                "stock": variant.stock,
                "is_active": variant.is_active,
            }
            for variant in sorted(product.variants, key=lambda entry: entry.sort_order)
        ],
    }


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
async def create_product(
    session: AsyncSession, actor: Profile, payload: ProductCreateIn
) -> Product:
    category = await _require_category(session, payload.category_id)
    brand = await _require_brand(session, payload.brand_id) if payload.brand_id else None
    _check_prices(payload.mrp_paise, payload.price_paise)

    product = Product(
        name=payload.name.strip(),
        slug=await _unique_product_slug(session, slugify(payload.slug or payload.name)),
        description=payload.description,
        category_id=category.id,
        brand_id=brand.id if brand else None,
        unit_label=payload.unit_label.strip(),
        mrp_paise=payload.mrp_paise,
        price_paise=payload.price_paise,
        stock=payload.stock,
        low_stock_threshold=payload.low_stock_threshold,
        images=payload.images,
        tags=payload.tags,
        is_active=payload.is_active,
        variants=_variant_rows(payload.variants),
    )
    product.category = category
    product.brand = brand
    product.search_text = _search_text(product)
    session.add(product)
    await session.flush()

    await audit.record(
        session,
        actor=actor,
        action="product.created",
        entity="product",
        entity_id=product.id,
        summary=product.name,
        after=snapshot(product),
    )
    return product


async def update_product(
    session: AsyncSession, actor: Profile, product_id: uuid.UUID, payload: ProductUpdateIn
) -> Product:
    product = await repo.get_product_admin(session, product_id)
    if product is None:
        raise NotFoundError("That product does not exist.", code="product_not_found")
    before = snapshot(product)
    sent = payload.model_fields_set

    if "category_id" in sent and payload.category_id is not None:
        product.category = await _require_category(session, payload.category_id)
        product.category_id = payload.category_id
    if "brand_id" in sent:
        if payload.brand_id is None:
            product.brand = None
            product.brand_id = None
        else:
            product.brand = await _require_brand(session, payload.brand_id)
            product.brand_id = payload.brand_id
    if "name" in sent and payload.name is not None:
        product.name = payload.name.strip()
    if "description" in sent and payload.description is not None:
        product.description = payload.description
    if "unit_label" in sent and payload.unit_label is not None:
        product.unit_label = payload.unit_label.strip()
    if payload.mrp_paise is not None:
        product.mrp_paise = payload.mrp_paise
    if payload.price_paise is not None:
        product.price_paise = payload.price_paise
    _check_prices(product.mrp_paise, product.price_paise)
    if payload.stock is not None:
        product.stock = payload.stock
    if payload.low_stock_threshold is not None:
        product.low_stock_threshold = payload.low_stock_threshold
    if payload.images is not None:
        product.images = [entry.strip() for entry in payload.images if entry.strip()]
    if payload.tags is not None:
        product.tags = [entry.strip() for entry in payload.tags if entry.strip()]
    if payload.is_active is not None:
        product.is_active = payload.is_active
    if payload.variants is not None:
        # Replace the option list wholesale: the shop is showing exactly these
        # packs on the product page, so a deleted variant must disappear.
        # The old rows go first — `(product_id, label)` is unique, so keeping
        # "1 kg" while adding "1 kg" back would collide mid-transaction.
        product.variants.clear()
        await session.flush()
        product.variants.extend(_variant_rows(payload.variants))
    product.search_text = _search_text(product)
    await session.flush()

    after = snapshot(product)
    await audit.record(
        session,
        actor=actor,
        action="product.updated",
        entity="product",
        entity_id=product.id,
        summary=product.name,
        before=before,
        after=after,
    )
    return product


async def delete_product(
    session: AsyncSession, actor: Profile, product_id: uuid.UUID
) -> tuple[str, str]:
    """Delete when nothing points at it, otherwise hide it. Never break history."""
    product = await repo.get_product_admin(session, product_id)
    if product is None:
        raise NotFoundError("That product does not exist.", code="product_not_found")
    before = snapshot(product)
    lines = await repo.order_lines_for_product(session, product_id)

    if lines:
        product.is_active = False
        product.search_text = _search_text(product)
        await session.flush()
        await audit.record(
            session,
            actor=actor,
            action="product.deactivated",
            entity="product",
            entity_id=product.id,
            summary=product.name,
            before=before,
            after=snapshot(product),
            note=f"{lines} past order line(s) reference this product",
        )
        return (
            "deactivated",
            f"{product.name} is in {lines} past order line(s), so it was hidden from the "
            "store instead of deleted. Its history stays intact.",
        )

    await session.delete(product)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="product.deleted",
        entity="product",
        entity_id=product_id,
        summary=before["name"] if isinstance(before["name"], str) else "",
        before=before,
    )
    return "deleted", "Product deleted."


def product_out(product: Product) -> ProductAdminOut:
    active_variants = [variant for variant in product.variants if variant.is_active]
    available = (
        sum(max(variant.stock, 0) for variant in active_variants)
        if active_variants
        else max(product.stock, 0)
    )
    return ProductAdminOut(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        category_id=product.category_id,
        category_name=product.category.name if product.category else "",
        category_slug=product.category.slug if product.category else "",
        brand_id=product.brand_id,
        brand_name=product.brand.name if product.brand else "",
        unit_label=product.unit_label,
        mrp_paise=product.mrp_paise,
        price_paise=product.price_paise,
        stock=product.stock,
        low_stock_threshold=product.low_stock_threshold,
        images=list(product.images or []),
        tags=list(product.tags or []),
        rating=float(product.rating or 0),
        is_active=product.is_active,
        variants=[
            AdminVariantOut(
                id=variant.id,
                label=variant.label,
                mrp_paise=variant.mrp_paise,
                price_paise=variant.price_paise,
                stock=variant.stock,
                sort_order=variant.sort_order,
                is_active=variant.is_active,
            )
            for variant in sorted(
                product.variants, key=lambda entry: (entry.sort_order, entry.label)
            )
        ],
        available_stock=available,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
async def create_category(session: AsyncSession, actor: Profile, payload: CategoryIn) -> Category:
    if payload.parent_id is not None:
        parent = await _require_category(session, payload.parent_id)
        if parent.parent_id is not None:
            raise ValidationError(
                "Categories nest one level deep — pick a department, not a subcategory.",
                code="category_too_deep",
                details={"field": "parent_id"},
            )
    category = Category(
        name=payload.name.strip(),
        slug=await _unique_category_slug(session, slugify(payload.slug or payload.name)),
        parent_id=payload.parent_id,
        emoji=payload.emoji,
        image_url=payload.image_url or None,
        description=payload.description or None,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    session.add(category)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="category.created",
        entity="category",
        entity_id=category.id,
        summary=category.name,
        after={
            "name": category.name,
            "slug": category.slug,
            "parent_id": str(category.parent_id or ""),
        },
    )
    return category


async def update_category(
    session: AsyncSession, actor: Profile, category_id: uuid.UUID, payload: CategoryUpdateIn
) -> Category:
    category = await repo.get_category(session, category_id)
    if category is None:
        raise NotFoundError("That category does not exist.", code="category_not_found")
    before = {
        "name": category.name,
        "emoji": category.emoji,
        "image_url": category.image_url,
        "description": category.description,
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "parent_id": str(category.parent_id or ""),
    }
    sent = payload.model_fields_set
    if "parent_id" in sent:
        if payload.parent_id is not None:
            if payload.parent_id == category.id:
                raise ValidationError(
                    "A category cannot be its own parent.",
                    code="category_self_parent",
                    details={"field": "parent_id"},
                )
            parent = await _require_category(session, payload.parent_id)
            if parent.parent_id is not None:
                raise ValidationError(
                    "Categories nest one level deep — pick a department, not a subcategory.",
                    code="category_too_deep",
                    details={"field": "parent_id"},
                )
        category.parent_id = payload.parent_id
    if payload.name is not None:
        category.name = payload.name.strip()
    if "emoji" in sent:
        category.emoji = (payload.emoji or "").strip() or None
    if "image_url" in sent:
        category.image_url = payload.image_url or None
    if "description" in sent:
        category.description = payload.description or None
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    await session.flush()

    after = {
        "name": category.name,
        "emoji": category.emoji,
        "image_url": category.image_url,
        "description": category.description,
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "parent_id": str(category.parent_id or ""),
    }
    await audit.record(
        session,
        actor=actor,
        action="category.updated",
        entity="category",
        entity_id=category.id,
        summary=category.name,
        before=before,
        after=after,
    )
    return category


async def delete_category(
    session: AsyncSession,
    actor: Profile,
    category_id: uuid.UUID,
    *,
    reassign_to: uuid.UUID | None,
) -> tuple[str, int, int]:
    """Delete a category, refusing unless its contents have somewhere to go."""
    category = await repo.get_category(session, category_id)
    if category is None:
        raise NotFoundError("That category does not exist.", code="category_not_found")
    products = await repo.category_product_count(session, category_id)
    children = await repo.category_child_count(session, category_id)

    if (products or children) and reassign_to is None:
        raise ConflictError(
            f"“{category.name}” still holds {products} product(s) and {children} "
            "subcategory(ies). Choose where they should move first.",
            code="category_not_empty",
            details={"products": products, "children": children},
        )
    if reassign_to is not None:
        if reassign_to == category_id:
            raise ValidationError(
                "A category cannot absorb itself.",
                code="category_self_parent",
                details={"field": "reassign_to"},
            )
        target = await _require_category(session, reassign_to)
        if target.parent_id == category_id:
            raise ValidationError(
                "Move the contents to a category outside the one being deleted.",
                code="category_reassign_into_child",
                details={"field": "reassign_to"},
            )
        await session.execute(
            update(Product).where(Product.category_id == category_id).values(category_id=target.id)
        )
        await session.execute(
            update(Category).where(Category.parent_id == category_id).values(parent_id=target.id)
        )

    name = category.name
    await session.delete(category)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="category.deleted",
        entity="category",
        entity_id=category_id,
        summary=name,
        before={"name": name, "products": products, "children": children},
        note=f"moved to {reassign_to}" if reassign_to else "",
    )
    return ("moved" if reassign_to else "deleted"), products, children


async def category_list(session: AsyncSession) -> list[CategoryAdminOut]:
    rows = await repo.list_categories_admin(session)
    products = await repo.product_counts_by_category(session)
    children = await repo.child_counts_by_category(session)
    names = {row.id: row.name for row in rows}
    return [
        CategoryAdminOut(
            id=row.id,
            name=row.name,
            slug=row.slug,
            parent_id=row.parent_id,
            parent_name=names.get(row.parent_id, "") if row.parent_id else "",
            emoji=row.emoji,
            image_url=row.image_url,
            description=row.description,
            sort_order=row.sort_order,
            is_active=row.is_active,
            product_count=products.get(row.id, 0),
            child_count=children.get(row.id, 0),
            updated_at=row.updated_at,
        )
        for row in sorted(
            rows, key=lambda entry: (entry.parent_id is not None, entry.sort_order, entry.name)
        )
    ]


# --------------------------------------------------------------------------- #
# Brands
# --------------------------------------------------------------------------- #
async def create_brand(session: AsyncSession, actor: Profile, payload: BrandIn) -> Brand:
    name = payload.name.strip()
    if await repo.brand_name_exists(session, name):
        raise ConflictError(
            "A brand with that name already exists.",
            code="brand_exists",
            details={"field": "name"},
        )
    brand = Brand(
        name=name,
        slug=await _unique_brand_slug(session, slugify(payload.slug or name)),
        logo_url=payload.logo_url or None,
        is_active=payload.is_active,
    )
    session.add(brand)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="brand.created",
        entity="brand",
        entity_id=brand.id,
        summary=brand.name,
        after={"name": brand.name, "slug": brand.slug},
    )
    return brand


async def update_brand(
    session: AsyncSession, actor: Profile, brand_id: uuid.UUID, payload: BrandUpdateIn
) -> Brand:
    brand = await repo.get_brand(session, brand_id)
    if brand is None:
        raise NotFoundError("That brand does not exist.", code="brand_not_found")
    before = {"name": brand.name, "logo_url": brand.logo_url, "is_active": brand.is_active}
    if payload.name is not None:
        name = payload.name.strip()
        if await repo.brand_name_exists(session, name, exclude=brand_id):
            raise ConflictError(
                "A brand with that name already exists.",
                code="brand_exists",
                details={"field": "name"},
            )
        brand.name = name
    if "logo_url" in payload.model_fields_set:
        brand.logo_url = payload.logo_url or None
    if payload.is_active is not None:
        brand.is_active = payload.is_active
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="brand.updated",
        entity="brand",
        entity_id=brand.id,
        summary=brand.name,
        before=before,
        after={"name": brand.name, "logo_url": brand.logo_url, "is_active": brand.is_active},
    )
    return brand


async def delete_brand(session: AsyncSession, actor: Profile, brand_id: uuid.UUID) -> None:
    brand = await repo.get_brand(session, brand_id)
    if brand is None:
        raise NotFoundError("That brand does not exist.", code="brand_not_found")
    in_use = await repo.brand_product_count(session, brand_id)
    if in_use:
        raise ConflictError(
            f"{in_use} product(s) still use “{brand.name}”. Move them to another brand first.",
            code="brand_in_use",
            details={"products": in_use},
        )
    name = brand.name
    await session.delete(brand)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="brand.deleted",
        entity="brand",
        entity_id=brand_id,
        summary=name,
        before={"name": name},
    )


async def brand_list(session: AsyncSession) -> list[BrandAdminOut]:
    rows = await repo.list_brands_admin(session)
    counts = await repo.product_counts_by_brand(session)
    return [
        BrandAdminOut(
            id=row.id,
            name=row.name,
            slug=row.slug,
            logo_url=row.logo_url,
            is_active=row.is_active,
            product_count=counts.get(row.id, 0),
        )
        for row in rows
    ]


__all__ = [
    "brand_list",
    "category_list",
    "create_brand",
    "create_category",
    "create_product",
    "delete_brand",
    "delete_category",
    "delete_product",
    "product_out",
    "slugify",
    "snapshot",
    "update_brand",
    "update_category",
    "update_product",
]
