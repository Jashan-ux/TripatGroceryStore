"""The audit trail: every owner action, newest first."""

from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUserDep, SessionDep
from app.repositories import admin_tools as repo
from app.schemas.admin_ops import AuditEntryOut, AuditListOut

router = APIRouter(prefix="/admin/audit", tags=["admin"])


@router.get("", response_model=AuditListOut, summary="What changed, who changed it, when")
async def list_audit(
    _: AdminUserDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditListOut:
    rows, total = await repo.list_audit(session, page=page, page_size=page_size)
    return AuditListOut(
        items=[
            AuditEntryOut(
                id=row.id,
                actor_email=row.actor_email,
                action=row.action,
                entity=row.entity,
                entity_id=row.entity_id,
                summary=row.summary,
                before=row.before or {},
                after=row.after or {},
                note=row.note,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )
