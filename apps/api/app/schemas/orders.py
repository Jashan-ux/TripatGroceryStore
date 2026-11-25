"""Address, cart-quote and order models.

The client never sends money. `QuoteIn` carries product ids, optional variant ids
and quantities; every price, total and availability flag comes back from the
database. `OrderIn` is the same payload plus an address, so a tampered client can
change *what* it buys but never *what it pays*.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.common import APIModel

Pincode = Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
class AddressIn(APIModel):
    label: str = Field(default="Home", max_length=40)
    recipient_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=1, max_length=32, examples=["+91 87089-73386"])
    line1: str = Field(min_length=5, max_length=240)
    line2: str = Field(default="", max_length=240)
    landmark: str = Field(default="", max_length=120)
    pincode: Pincode
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_default: bool = False


class AddressOut(APIModel):
    id: uuid.UUID
    label: str
    recipient_name: str
    phone: str
    line1: str
    line2: str
    landmark: str
    pincode: str
    city: str
    state: str
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Cart → quote
# --------------------------------------------------------------------------- #
class CartLineIn(APIModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    quantity: int = Field(ge=1, le=99)


class QuoteIn(APIModel):
    items: list[CartLineIn] = Field(min_length=1, max_length=50)
    pincode: Pincode | None = None


class QuoteLineOut(APIModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    slug: str
    name: str
    unit_label: str
    variant_label: str
    image_url: str
    unit_price_paise: int
    mrp_paise: int
    quantity: int
    line_total_paise: int
    available_stock: int
    in_stock: bool
    #: `out_of_stock` | `partially_available` | `unavailable` | None
    issue: Literal["out_of_stock", "partially_available", "unavailable"] | None = None


class BlockingIssue(APIModel):
    #: `empty_cart` | `minimum_order` | `pincode` | `stock`
    code: Literal["empty_cart", "minimum_order", "pincode", "stock"]
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class QuoteOut(APIModel):
    lines: list[QuoteLineOut]
    item_count: int
    subtotal_paise: int
    delivery_fee_paise: int
    discount_paise: int
    total_paise: int
    minimum_order_paise: int
    shortfall_paise: int
    delivery_days: int
    deliver_by: date
    pincode: str | None = None
    pincode_serviceable: bool | None = None
    blocking_issues: list[BlockingIssue]
    can_checkout: bool


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
class OrderIn(APIModel):
    items: list[CartLineIn] = Field(min_length=1, max_length=50)
    address_id: uuid.UUID
    customer_note: str = Field(default="", max_length=500)


class OrderItemOut(APIModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    name: str
    unit_label: str
    variant_label: str
    image_url: str
    unit_price_paise: int
    mrp_paise: int
    quantity: int
    line_total_paise: int


class OrderEventOut(APIModel):
    status: str
    actor: str
    note: str
    created_at: datetime


class AddressSnapshotOut(APIModel):
    label: str = ""
    recipient_name: str = ""
    phone: str = ""
    line1: str = ""
    line2: str = ""
    landmark: str = ""
    pincode: str = ""
    city: str = ""
    state: str = ""


class OrderOut(APIModel):
    id: uuid.UUID
    order_number: str
    status: str
    payment_method: str
    payment_status: str
    subtotal_paise: int
    delivery_fee_paise: int
    discount_paise: int
    total_paise: int
    item_count: int
    customer_name: str
    customer_phone: str
    customer_note: str
    address: AddressSnapshotOut
    delivery_days: int
    deliver_by: date | None = None
    placed_at: datetime
    cancelled_at: datetime | None = None
    cancelled_reason: str
    items: list[OrderItemOut]
    events: list[OrderEventOut]


class OrderSummaryOut(APIModel):
    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    total_paise: int
    item_count: int
    placed_at: datetime
    deliver_by: date | None = None
    first_item_name: str
    first_item_image_url: str


class OrderListOut(APIModel):
    items: list[OrderSummaryOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderCancelIn(APIModel):
    reason: str = Field(default="", max_length=300)
