"""Profile queries.

Every helper takes the session and returns ORM objects; no business rules here.
"""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import Profile


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    return cast("Profile | None", await session.get(Profile, user_id))


async def get_profile_by_email(session: AsyncSession, email: str) -> Profile | None:
    return cast(
        "Profile | None",
        await session.scalar(select(Profile).where(Profile.email == email.strip().lower())),
    )


async def get_profile_by_referral_code(session: AsyncSession, code: str) -> Profile | None:
    return cast(
        "Profile | None",
        await session.scalar(select(Profile).where(Profile.referral_code == code.upper())),
    )


async def phone_exists(session: AsyncSession, phone: str, *, exclude_user: uuid.UUID) -> bool:
    stmt = select(Profile.id).where(Profile.phone == phone, Profile.id != exclude_user)
    return await session.scalar(stmt) is not None


async def referral_code_exists(session: AsyncSession, code: str) -> bool:
    return await session.scalar(select(Profile.id).where(Profile.referral_code == code)) is not None
