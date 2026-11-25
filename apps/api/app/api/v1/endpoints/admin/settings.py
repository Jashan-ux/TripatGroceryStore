"""The store settings the owner edits — no redeploy, every change audit-logged."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUserDep, SessionDep
from app.schemas.admin_ops import SettingsOut, SettingsPatchIn
from app.services import admin_settings as service

router = APIRouter(prefix="/admin/settings", tags=["admin"])


@router.get("", response_model=SettingsOut, summary="Every number the shop runs on")
async def read_settings(_: AdminUserDep, session: SessionDep) -> SettingsOut:
    return await service.read(session)


@router.patch(
    "",
    response_model=SettingsOut,
    summary="Change settings; the next checkout uses them immediately",
)
async def update_settings(
    user: AdminUserDep, session: SessionDep, payload: SettingsPatchIn
) -> SettingsOut:
    updated = await service.update(session, user.profile, payload)
    await session.commit()
    return updated
