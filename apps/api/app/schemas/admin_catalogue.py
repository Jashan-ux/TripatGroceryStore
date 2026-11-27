"""Admin catalogue contracts: products, variants, categories, brands, bulk add.

Money is integer paise on the wire, exactly like the storefront. The bulk importer
is the one place a rupee amount is accepted, because that is the number a merchant
types into a spreadsheet — and it is converted to paise exactly, never via float.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel

#: A product is described by the same handful of fields whether it is created from
#: the inline row, the edit dialog or the bulk file.
MAX_PRICE_PAISE = 10_00_00_000  # ₹1 crore — a typo guard, not a business limit


class VariantIn(APIModel):
    label: str = Field(min_length=1, max_length=40, description="100 g, 1 kg, pack of 6…")
    mrp_paise: int = Field(default=0, ge=0, le=MAX_PRICE_PAISE)
    price_paise: int = Field(default=0, ge=0, le=MAX_PRICE_PAISE)
    stock: int = Field(default=0, ge=0, le=1_000_000)
    sort_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True


class AdminVariantOut(APIModel):
    id: uuid.UUID
    label: str
    mrp_paise: int
    price_paise: int
    stock: int
    sort_order: int
    is_active: bool


class ProductCreateIn(APIModel):
    """One product, as the inline category row or the dialog sends it."""

    name: str = Field(min_length=1, max_length=200)
    category_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    description: str = Field(default="", max_length=4000)
    unit_label: str = Field(default="", max_length=40)
    mrp_paise: int = Field(default=0, ge=0, le=MAX_PRICE_PAISE)
    price_paise: int = Field(ge=0, le=MAX_PRICE_PAISE)
    stock: int = Field(default=0, ge=0, le=1_000_000)
    low_stock_threshold: int = Field(default=10, ge=0, le=100_000)
    images: list[str] = Field(default_factory=list, max_length=8)
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_active: bool = True
    variants: list[VariantIn] = Field(default_factory=list, max_length=20)
    #: Optional: the slug is derived from the name when the shop does not care.
    slug: str | None = Field(default=None, max_length=220)

    @field_validator("images", "tags")
    @classmethod
    def _trim(cls, value: list[str]) -> list[str]:
        return [entry.strip() for entry in value if entry.strip()]


class ProductUpdateIn(APIModel):
    """Every field optional; only what the shop actually sent is changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    unit_label: str | None = Field(default=None, max_length=40)
    mrp_paise: int | None = Field(default=None, ge=0, le=MAX_PRICE_PAISE)
    price_paise: int | None = Field(default=None, ge=0, le=MAX_PRICE_PAISE)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    low_stock_threshold: int | None = Field(default=None, ge=0, le=100_000)
    images: list[str] | None = Field(default=None, max_length=8)
    tags: list[str] | None = Field(default=None, max_length=20)
    is_active: bool | None = None
    #: Sent as a whole list: the storefront shows exactly these options.
    variants: list[VariantIn] | None = Field(default=None, max_length=20)


class InventoryStockPatchIn(APIModel):
    stock: int = Field(ge=0, le=1_000_000)
    note: str = Field(default="", max_length=300)


class ProductAdminOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    category_id: uuid.UUID
    category_name: str = ""
    category_slug: str = ""
    brand_id: uuid.UUID | None = None
    brand_name: str = ""
    unit_label: str
    mrp_paise: int
    price_paise: int
    stock: int
    low_stock_threshold: int
    images: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rating: float = 0
    is_active: bool
    variants: list[AdminVariantOut] = Field(default_factory=list)
    #: Stock the storefront will offer: the sum of active variants when there are any.
    available_stock: int = 0
    created_at: datetime
    updated_at: datetime


class AdminProductListOut(APIModel):
    items: list[ProductAdminOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductDeleteOut(APIModel):
    id: uuid.UUID
    #: ``deleted`` means the row is gone; ``deactivated`` means orders reference it,
    #: so it was hidden from the storefront instead of breaking history.
    outcome: Literal["deleted", "deactivated"]
    message: str


class CategoryIn(APIModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    emoji: str | None = Field(default=None, max_length=16)
    image_url: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_active: bool = True
    slug: str | None = Field(default=None, max_length=140)

    @field_validator("emoji")
    @classmethod
    def _emoji_or_none(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class CategoryUpdateIn(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    emoji: str | None = Field(default=None, max_length=16)
    image_url: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None


class CategoryAdminOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None = None
    parent_name: str = ""
    emoji: str | None = None
    image_url: str | None = None
    description: str | None = None
    sort_order: int
    is_active: bool
    product_count: int = 0
    child_count: int = 0
    updated_at: datetime


class AdminCategoryListOut(APIModel):
    categories: list[CategoryAdminOut]


class CategoryDeleteOut(APIModel):
    id: uuid.UUID
    outcome: Literal["deleted", "moved"]
    products_moved: int = 0
    children_moved: int = 0
    message: str


class BrandIn(APIModel):
    name: str = Field(min_length=1, max_length=120)
    logo_url: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    slug: str | None = Field(default=None, max_length=140)


class BrandUpdateIn(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    logo_url: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class BrandAdminOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    is_active: bool
    product_count: int = 0


class BrandListOut(APIModel):
    brands: list[BrandAdminOut]


class BrandDeleteOut(APIModel):
    id: uuid.UUID
    outcome: Literal["deleted"]
    message: str


class BulkIn(APIModel):
    """A pasted or uploaded CSV. ``dry_run`` is the default: nothing is written."""

    csv: str = Field(min_length=1, max_length=2_000_000)
    dry_run: bool = True


class BulkRowOut(APIModel):
    line: int = Field(description="1-based line in the pasted text, header included")
    status: Literal["ok", "error"]
    name: str = ""
    slug: str = ""
    category: str = ""
    errors: list[str] = Field(default_factory=list)
    product_id: uuid.UUID | None = None


class BulkResultOut(APIModel):
    committed: bool
    total: int
    valid: int
    invalid: int
    rows: list[BulkRowOut]
    created: int = 0
    message: str = ""


class ImageOut(APIModel):
    url: str
    width: int
    height: int
    bytes: int
    content_type: str = "image/webp"
