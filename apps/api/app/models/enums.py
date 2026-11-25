"""Enums shared by the ORM models and the migrations.

They live in one module so a value can never be defined twice. ``native_enum``
is on: Postgres enforces the values, which is the point.
"""

from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    customer = "customer"
    admin = "admin"
    #: Reserved for a later delivery-person view. No code path assigns it yet.
    delivery = "delivery"


class LoyaltyTier(enum.StrEnum):
    none = "none"
    gold = "gold"
    platinum = "platinum"
    diamond = "diamond"


class OrderStatus(enum.StrEnum):
    processing = "processing"
    shipped = "shipped"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    returned = "returned"


class PaymentMethod(enum.StrEnum):
    cod = "cod"


class PaymentStatus(enum.StrEnum):
    pending = "pending"
    paid = "paid"


class ReturnStatus(enum.StrEnum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    received_credited = "received_credited"


class ScratchCardStatus(enum.StrEnum):
    locked = "locked"
    ready = "ready"
    revealed = "revealed"
    used = "used"
    void = "void"


class OfferAudience(enum.StrEnum):
    all = "all"
    gold = "gold"
    platinum = "platinum"
    diamond = "diamond"
