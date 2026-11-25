"""The shop's feedback inbox."""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from app.api.deps import AdminUserDep, SessionDep
from app.models.enums import FeedbackStatus
from app.schemas.admin_ops import FeedbackListOut, FeedbackOut
from app.services import feedback as service

router = APIRouter(prefix="/admin/feedback", tags=["admin"])

FeedbackId = Annotated[uuid.UUID, Path(description="Feedback id")]
StatusFilter = Literal["new", "read"]


@router.get("", response_model=FeedbackListOut, summary="Messages from customers")
async def list_feedback(
    _: AdminUserDep,
    session: SessionDep,
    status: Annotated[StatusFilter | None, Query(description="new or read")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FeedbackListOut:
    items, total = await service.list_page(
        session,
        status=FeedbackStatus(status) if status else None,
        page=page,
        page_size=page_size,
    )
    return FeedbackListOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/{feedback_id}/read", response_model=FeedbackOut, summary="Mark one as read")
async def mark_read(
    user: AdminUserDep, session: SessionDep, feedback_id: FeedbackId
) -> FeedbackOut:
    row = await service.mark_read(session, feedback_id=feedback_id, actor=user.profile)
    await session.commit()
    return row
