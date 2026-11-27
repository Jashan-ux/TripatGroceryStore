"""Admin-only endpoints.

Every route here is mounted under ``/admin`` and depends on ``require_admin``,
so a single dependency protects the whole surface. Phase 1 exposes only an
identity probe — the real tools arrive in Phases 3–6.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUserDep
from app.schemas.profile import ProfileOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/whoami",
    response_model=ProfileOut,
    summary="Confirm the caller is the store owner",
)
async def whoami(user: AdminUserDep) -> ProfileOut:
    profile = user.profile
    return ProfileOut(
        id=profile.id,
        name=profile.name,
        email=profile.email,
        phone=profile.phone,
        role=profile.role.value,
        referral_code=profile.referral_code,
        lifetime_spend_paise=profile.lifetime_spend_paise,
        loyalty_tier=profile.loyalty_tier.value,
        notification_prefs=profile.notification_prefs or {},
        has_phone=bool(profile.phone),
        created_at=profile.created_at,
    )
