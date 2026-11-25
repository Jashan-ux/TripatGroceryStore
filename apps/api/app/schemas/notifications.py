"""Notification models exposed to the client."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class NotificationOut(APIModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    #: Deep link the UI should follow when tapped (``/orders/<id>``, ``/admin/orders``).
    href: str
    order_id: uuid.UUID | None = None
    read: bool
    created_at: datetime


class NotificationListOut(APIModel):
    items: list[NotificationOut]
    unread_count: int
    total: int
    page: int
    page_size: int
    total_pages: int


class UnreadCountOut(APIModel):
    unread_count: int = Field(ge=0)


class MarkAllReadOut(APIModel):
    marked: int = Field(ge=0)
