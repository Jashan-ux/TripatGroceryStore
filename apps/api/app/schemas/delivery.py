"""Contracts for the narrowly-scoped delivery-person workspace."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.orders import AddressSnapshotOut


class DeliveryProfileOut(APIModel):
    id: uuid.UUID
    name: str
    phone: str | None = None


class DeliveryCandidateOut(DeliveryProfileOut):
    email: str


class PromoteDeliveryProfileIn(APIModel):
    profile_id: uuid.UUID


class DeliveryOrderItemOut(APIModel):
    name: str
    unit_label: str
    variant_label: str
    quantity: int
    line_total_paise: int


class DeliveryOrderOut(APIModel):
    id: uuid.UUID
    order_number: str
    status: str
    payment_method: str
    payment_status: str
    total_paise: int
    item_count: int
    customer_name: str
    customer_phone: str
    address: AddressSnapshotOut
    items: list[DeliveryOrderItemOut]
    out_for_delivery_at: datetime | None = None
    delivered_at: datetime | None = None


class DeliveryOrderListOut(APIModel):
    items: list[DeliveryOrderOut]
    total: int


class DeliveryAssignmentIn(APIModel):
    profile_id: uuid.UUID | None = Field(
        description="Delivery profile id, or null to unassign the order."
    )
