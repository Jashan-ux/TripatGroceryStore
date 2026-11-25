"""The caller's own account: profile, name, phone, notification preferences.

There is deliberately no ``/me/{id}`` — a user can only ever address themselves,
which removes the entire class of IDOR bugs from this router.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, CurrentUserDep, SessionDep
from app.schemas.profile import NotificationPrefsIn, PhoneIn, ProfileOut, ProfileUpdateIn
from app.services import profiles as service

router = APIRouter(prefix="/me", tags=["me"])


def profile_out(user: CurrentUser) -> ProfileOut:
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


@router.get("", response_model=ProfileOut, summary="My profile")
async def get_me(user: CurrentUserDep) -> ProfileOut:
    return profile_out(user)


@router.patch("", response_model=ProfileOut, summary="Update my name")
async def update_me(
    user: CurrentUserDep, session: SessionDep, payload: ProfileUpdateIn
) -> ProfileOut:
    profile = await service.update_name(session, user.profile, payload.name)
    user.profile.name = profile.name
    return profile_out(user)


@router.post("/phone", response_model=ProfileOut, summary="Add or change my mobile number")
async def set_phone(user: CurrentUserDep, session: SessionDep, payload: PhoneIn) -> ProfileOut:
    profile = await service.set_phone(session, user.profile, payload.phone)
    user.profile.phone = profile.phone
    return profile_out(user)


@router.put(
    "/notification-preferences",
    response_model=ProfileOut,
    summary="Notification consent (DPDP)",
)
async def set_notification_preferences(
    user: CurrentUserDep, session: SessionDep, payload: NotificationPrefsIn
) -> ProfileOut:
    user.profile.notification_prefs = payload.model_dump()
    await session.commit()
    await session.refresh(user.profile)
    return profile_out(user)
