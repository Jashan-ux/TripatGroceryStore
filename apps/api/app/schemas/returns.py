"""Models for returns (customer asks, owner decides, wallet pays)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

ReturnStatusOut = Literal["requested", "approved", "rejected", "received_credited"]


class ReturnItemIn(APIModel):
    order_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=99)


class ReturnRequestIn(APIModel):
    items: list[ReturnItemIn] = Field(min_length=1, max_length=50)
    reason: str = Field(default="", max_length=500)


class ReturnItemOut(APIModel):
    order_item_id: uuid.UUID
    name: str
    quantity: int
    refund_paise: int


class ReturnOut(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str = ""
    status: ReturnStatusOut
    reason: str = ""
    refund_paise: int
    decision_note: str = ""
    requested_at: datetime
    decided_at: datetime | None = None
    received_at: datetime | None = None
    items: list[ReturnItemOut]


class ReturnListOut(APIModel):
    returns: list[ReturnOut]


class AdminReturnOut(ReturnOut):
    customer_name: str = ""
    customer_phone: str = ""


class AdminReturnListOut(APIModel):
    items: list[AdminReturnOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminReturnDecisionIn(APIModel):
    approve: bool
    note: str = Field(default="", max_length=300)


class AdminReturnReceiveIn(APIModel):
    note: str = Field(default="", max_length=300)
