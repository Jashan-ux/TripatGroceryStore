"""Public catalogue: read-only, no authentication required.

Only active rows are ever returned. Prices are read from the server's own
columns — nothing here trusts a client value.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models.catalogue import Category, Product
from app.repositories.catalogue import ProductFilters
from app.schemas.catalogue import (
    BrandOut,
    CategoryOut,
    CategoryTreeOut,
    HomeOut,
    HomeRailOut,
    ProductCardOut,
    ProductDetailOut,
    ProductListOut,
    VariantOut,
)
from app.services import catalogue as service

router = APIRouter(tags=["catalogue"])

MAX_PAGE_SIZE = 48


def category_out(category: Category) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        name=category.name,
        slug=category.slug,
        emoji=category.emoji,
        image_url=category.image_url,
        description=category.description,
        sort_order=category.sort_order,
        parent_id=category.parent_id,
    )


def product_card(product: Product) -> ProductCardOut:
    stock = service.effective_stock(product)
    first_image = product.images[0] if product.images else None
    return ProductCardOut(
        id=product.id,
        name=product.name,
        slug=product.slug,
        category_slug=product.category.slug if product.category else "",
        category_name=product.category.name if product.category else "",
        brand_name=product.brand.name if product.brand else None,
        unit_label=product.unit_label,
        mrp_paise=product.mrp_paise,
        price_paise=product.price_paise,
        discount_percent=service.discount_percent(product.mrp_paise, product.price_paise),
        image_url=first_image,
        rating=service.rating_value(product.rating),
        stock=stock,
        in_stock=stock > 0,
        tags=list(product.tags or []),
        has_variants=any(v.is_active for v in product.variants),
    )


def product_detail(product: Product) -> ProductDetailOut:
    card = product_card(product)
    threshold = product.low_stock_threshold or 0
    return ProductDetailOut(
        **card.model_dump(),
        description=product.description or "",
        images=list(product.images or []),
        variants=[
            VariantOut(**service.variant_payload(variant))
            for variant in sorted(product.variants, key=lambda v: (v.sort_order, v.label))
            if variant.is_active
        ],
        low_stock=0 < card.stock <= threshold,
    )


@router.get("/categories", response_model=list[CategoryTreeOut], summary="Category tree")
async def list_categories(session: SessionDep) -> list[CategoryTreeOut]:
    nodes = await service.category_tree(session)
    return [
        CategoryTreeOut(
            **category_out(node.category).model_dump(),
            children=[category_out(child) for child in node.children],
        )
        for node in nodes
    ]


@router.get(
    "/categories/{slug}",
    response_model=CategoryTreeOut,
    summary="One category with its subcategories",
)
async def get_category(
    session: SessionDep, slug: Annotated[str, Path(max_length=140)]
) -> CategoryTreeOut:
    nodes = await service.category_tree(session)
    for node in nodes:
        if node.category.slug == slug:
            return CategoryTreeOut(
                **category_out(node.category).model_dump(),
                children=[category_out(child) for child in node.children],
            )
        for child in node.children:
            if child.slug == slug:
                return CategoryTreeOut(**category_out(child).model_dump(), children=[])
    raise NotFoundError("Category not found.", code="category_not_found")


@router.get("/brands", response_model=list[BrandOut], summary="Brands that have products")
async def list_brands(session: SessionDep) -> list[BrandOut]:
    brands = await service.active_brands(session)
    return [
        BrandOut(id=brand.id, name=brand.name, slug=brand.slug, logo_url=brand.logo_url)
        for brand in brands
    ]


@router.get("/products", response_model=ProductListOut, summary="Search and filter products")
async def list_products(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=80, description="Free-text search")] = None,
    category: Annotated[str | None, Query(max_length=140, description="Category slug")] = None,
    brand: Annotated[str | None, Query(max_length=140, description="Brand slug")] = None,
    min_price_paise: Annotated[int | None, Query(ge=0, le=10_000_000)] = None,
    max_price_paise: Annotated[int | None, Query(ge=0, le=10_000_000)] = None,
    tags: Annotated[str | None, Query(max_length=200, description="Comma separated")] = None,
    in_stock: Annotated[bool, Query()] = False,
    sort: Annotated[
        Literal["popular", "rating", "price_asc", "price_desc", "newest", "name"], Query()
    ] = "popular",
    page: Annotated[int, Query(ge=1, le=200)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> ProductListOut:
    filters = ProductFilters(
        q=q,
        category_slug=category,
        brand_slug=brand,
        min_price_paise=min_price_paise,
        max_price_paise=max_price_paise,
        tags=tuple(tag.strip() for tag in (tags or "").split(",") if tag.strip()),
        in_stock_only=in_stock,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    items, total = await service.search_products(session, filters)
    total_pages = (total + page_size - 1) // page_size if total else 0
    return ProductListOut(
        items=[product_card(product) for product in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/products/{slug}", response_model=ProductDetailOut, summary="Product detail")
async def get_product(
    session: SessionDep, slug: Annotated[str, Path(max_length=220)]
) -> ProductDetailOut:
    product = await service.product_by_slug(session, slug)
    return product_detail(product)


@router.get("/home", response_model=HomeOut, summary="Home page payload (categories + rails)")
async def home(session: SessionDep) -> HomeOut:
    nodes = await service.category_tree(session)
    rails = await service.home_rails(session)
    return HomeOut(
        categories=[
            CategoryTreeOut(
                **category_out(node.category).model_dump(),
                children=[category_out(child) for child in node.children],
            )
            for node in nodes
        ],
        rails=[
            HomeRailOut(
                category=category_out(category), products=[product_card(p) for p in products]
            )
            for category, products in rails
        ],
    )
