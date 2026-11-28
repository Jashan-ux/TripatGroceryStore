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
    accepted = "accepted"
    packing = "packing"
    shipped = "shipped"  # Legacy persisted state; new transitions use accepted/packing.
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


class ReferralStatus(enum.StrEnum):
    #: The friend has joined but their first order is not delivered yet.
    pending = "pending"
    #: The referrer has been paid; nothing left to do.
    credited = "credited"
    #: Called off before it could pay (the friend's order was cancelled).
    void = "void"


class WalletReason(enum.StrEnum):
    #: Credit: the referrer's reward once the friend's first order lands.
    referral_bonus = "referral_bonus"
    #: Credit: a scratch card the customer rubbed off.
    scratch_card = "scratch_card"
    #: Credit: the shop received a return.
    return_refund = "return_refund"
    #: Debit: part of an order paid from the wallet instead of cash.
    order_payment = "order_payment"
    #: Credit/debit: the owner's correction, with a note.
    adjustment = "adjustment"


class NotificationKind(enum.StrEnum):
    #: Customer: "we have your order".
    order_placed = "order_placed"
    #: Customer: shipped / out for delivery / delivered / returned.
    order_status = "order_status"
    #: Customer: called off, by them or by the shop.
    order_cancelled = "order_cancelled"
    #: Owner: an order came in.
    new_order = "new_order"
    #: Customer: a message the shop composed (offers, announcements).
    offer = "offer"
    #: Anything the shop wants to tell people later (offers, low stock).
    system = "system"


class EmailStatus(enum.StrEnum):
    queued = "queued"
    sent = "sent"
    #: No provider configured (or email switched off) — recorded, not retried.
    skipped = "skipped"
    failed = "failed"


class OfferAudience(enum.StrEnum):
    all = "all"
    gold = "gold"
    platinum = "platinum"
    diamond = "diamond"


class FeedbackKind(enum.StrEnum):
    general = "general"
    order = "order"
    product = "product"
    other = "other"


class FeedbackStatus(enum.StrEnum):
    #: Nobody has looked at it yet.
    new = "new"
    #: The owner has read it (the row keeps the time it happened).
    read = "read"
