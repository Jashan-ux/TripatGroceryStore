"""The bell: one person's notifications.

Every route is scoped to the caller's profile — there is no ``/notifications/{id}``
that can be read or acknowledged by somebody else, and the id lookup filters by
``profile_id`` so a stranger's id is a 404, not a leak.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.notifications import (
    MarkAllReadOut,
    NotificationListOut,
    NotificationOut,
    UnreadCountOut,
)
from app.services import notifications as service

router = APIRouter(prefix="/notifications", tags=["notifications"])

NotificationId = Annotated[uuid.UUID, Path(description="Notification id")]


@router.get("", response_model=NotificationListOut, summary="My notifications, newest first")
async def list_notifications(
    user: CurrentUserDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> NotificationListOut:
    return await service.list_for_profile(session, user.profile, page=page, page_size=page_size)


@router.get("/unread-count", response_model=UnreadCountOut, summary="Red dot number")
async def unread_count(user: CurrentUserDep, session: SessionDep) -> UnreadCountOut:
    return UnreadCountOut(unread_count=await service.unread_count(session, user.profile))


@router.post("/{notification_id}/ack", response_model=NotificationOut, summary="Mark one read")
async def ack_notification(
    user: CurrentUserDep, session: SessionDep, notification_id: NotificationId
) -> NotificationOut:
    notification = await service.mark_read(session, user.profile, notification_id)
    return service.notification_out(notification)


@router.post("/read-all", response_model=MarkAllReadOut, summary="Clear the bell")
async def read_all(user: CurrentUserDep, session: SessionDep) -> MarkAllReadOut:
    return MarkAllReadOut(marked=await service.mark_all_read(session, user.profile))
