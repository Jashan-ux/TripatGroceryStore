"""Enums shared by the ORM models and the migrations.

They live in one module so a value can never be defined twice. ``native_enum``
is on: Postgres enforces the values, which is the point.
"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    customer = "customer"
    admin = "admin"
    #: Reserved for a later delivery-person view. No code path assigns it yet.
    delivery = "delivery"


class LoyaltyTier(str, enum.Enum):
    none = "none"
    gold = "gold"
    platinum = "platinum"
    diamond = "diamond"


class OrderStatus(str, enum.Enum):
    processing = "processing"
    shipped = "shipped"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    returned = "returned"


class PaymentMethod(str, enum.Enum):
    cod = "cod"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"


class ReturnStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    received_credited = "received_credited"


class ScratchCardStatus(str, enum.Enum):
    locked = "locked"
    ready = "ready"
    revealed = "revealed"
    used = "used"
    void = "void"


class OfferAudience(str, enum.Enum):
    all = "all"
    gold = "gold"
    platinum = "platinum"
    diamond = "diamond"
