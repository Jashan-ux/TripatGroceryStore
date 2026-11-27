"""Public catalogue response models."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class CategoryOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    emoji: str | None = None
    image_url: str | None = None
    description: str | None = None
    sort_order: int = 0
    parent_id: uuid.UUID | None = None


class CategoryTreeOut(CategoryOut):
    children: list[CategoryOut] = Field(default_factory=list)


class BrandOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None


class VariantOut(APIModel):
    id: uuid.UUID
    label: str
    mrp_paise: int = Field(ge=0)
    price_paise: int = Field(ge=0)
    stock: int = Field(ge=0)
    discount_percent: int = Field(ge=0, le=100)
    is_active: bool = True
    sort_order: int = 0


class ProductCardOut(APIModel):
    """Exactly what a grid card needs — no description, keeps payloads small."""

    id: uuid.UUID
    name: str
    slug: str
    category_slug: str
    category_name: str
    brand_name: str | None = None
    unit_label: str
    mrp_paise: int = Field(ge=0)
    price_paise: int = Field(ge=0)
    discount_percent: int = Field(ge=0, le=100)
    image_url: str | None = None
    rating: float = Field(ge=0, le=5)
    stock: int = Field(ge=0)
    in_stock: bool
    tags: list[str] = Field(default_factory=list)
    has_variants: bool = False


class ProductDetailOut(ProductCardOut):
    description: str = ""
    images: list[str] = Field(default_factory=list)
    variants: list[VariantOut] = Field(default_factory=list)
    low_stock: bool = False


class ProductListOut(APIModel):
    items: list[ProductCardOut]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class HomeRailOut(APIModel):
    category: CategoryOut
    products: list[ProductCardOut]


class HomeOut(APIModel):
    categories: list[CategoryTreeOut]
    rails: list[HomeRailOut]


class SortOption(APIModel):
    value: str
    label: str


SortKey = Literal["popular", "rating", "price_asc", "price_desc", "newest", "name"]
