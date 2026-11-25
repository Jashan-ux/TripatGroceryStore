"""Profile business rules: first-login bootstrap, name/phone, referral codes."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, ValidationError
from app.core.logging import get_logger
from app.core.security import TokenClaims
from app.models.catalogue import Profile
from app.models.enums import UserRole
from app.repositories import profiles as repo

logger = get_logger(__name__)

#: Ambiguous characters (0/O, 1/I/L) are excluded so codes can be read aloud.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6

PHONE_PREFIXES = ("6", "7", "8", "9")


def normalise_phone(raw: str) -> str:
    """Return a bare 10-digit Indian mobile number or raise a clear error.

    Accepts "+91 87089-73386", "08708973386", "8708973386".
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        raise ValidationError(
            "Enter a 10-digit mobile number.",
            code="invalid_phone",
            details={"field": "phone"},
        )
    if not digits.startswith(PHONE_PREFIXES):
        raise ValidationError(
            "An Indian mobile number starts with 6, 7, 8 or 9.",
            code="invalid_phone",
            details={"field": "phone"},
        )
    return digits


def generate_referral_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


async def _unique_referral_code(session: AsyncSession) -> str:
    for _ in range(8):
        code = generate_referral_code()
        if not await repo.referral_code_exists(session, code):
            return code
    # 32^6 combinations; reaching here means something is badly wrong.
    raise ConflictError("Could not allocate a referral code. Please try again.")


def bootstrap_role(email: str) -> UserRole:
    """Admin bootstrap.

    The brief allows granting admin from ``ADMIN_EMAILS`` at seed time. The
    first profile created for one of those addresses *is* that seed step, and it
    runs only at creation — later changes to the env var never elevate an
    existing account, and the role is read from the database on every request.
    """
    return UserRole.admin if email in get_settings().admin_emails else UserRole.customer


async def ensure_profile(session: AsyncSession, claims: TokenClaims) -> Profile:
    """Get the caller's profile, creating it on first authenticated request."""
    existing = await repo.get_profile(session, claims.sub)
    if existing is not None:
        return existing

    profile = Profile(
        id=claims.sub,
        email=claims.email,
        name=claims.display_name,
        role=bootstrap_role(claims.email),
        referral_code=await _unique_referral_code(session),
        notification_prefs={"email": True, "push": True, "offers": True},
    )
    session.add(profile)
    try:
        await session.commit()
    except IntegrityError:
        # Two requests raced on first login — the other one won.
        await session.rollback()
        raced = await repo.get_profile(session, claims.sub)
        if raced is None:  # pragma: no cover - defensive
            raise
        return raced

    await session.refresh(profile)
    logger.info("profile_created", user_id=str(profile.id), role=profile.role.value)
    return profile


async def update_name(session: AsyncSession, profile: Profile, name: str) -> Profile:
    cleaned = " ".join(name.split())
    if len(cleaned) < 2:
        raise ValidationError(
            "Please enter your name.", code="invalid_name", details={"field": "name"}
        )
    if len(cleaned) > 120:
        raise ValidationError(
            "That name is too long.", code="invalid_name", details={"field": "name"}
        )
    profile.name = cleaned
    await session.commit()
    await session.refresh(profile)
    return profile


async def set_phone(session: AsyncSession, profile: Profile, raw_phone: str) -> Profile:
    phone = normalise_phone(raw_phone)
    if await repo.phone_exists(session, phone, exclude_user=profile.id):
        raise ConflictError(
            "That mobile number is already linked to another account. "
            "Please sign in with it, or call the store.",
            code="phone_already_used",
            details={"field": "phone"},
        )
    profile.phone = phone
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "That mobile number is already linked to another account.",
            code="phone_already_used",
            details={"field": "phone"},
        ) from exc
    await session.refresh(profile)
    logger.info("phone_added", user_id=str(profile.id))
    return profile


async def touch_last_seen(session: AsyncSession, profile: Profile) -> None:
    profile.last_seen_at = datetime.now(tz=UTC)
    await session.commit()
