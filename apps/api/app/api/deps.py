"""Request dependencies: authentication, the current profile, and admin access.

Authorisation is deny-by-default. Only routers that explicitly depend on
``CurrentUser`` or ``AdminUser`` are protected; everything else is public
read-only catalogue data.

Ownership is enforced inside queries (``user_id`` in the ``WHERE``), never by
fetching a row and comparing afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.core.security import TokenClaims, verify_token
from app.db.session import get_session, get_sessionmaker
from app.models.catalogue import Profile
from app.models.enums import UserRole
from app.repositories.profiles import get_profile
from app.services.profiles import ensure_profile

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Supabase access token (`Authorization: Bearer <jwt>`).",
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_optional_session() -> AsyncIterator[AsyncSession | None]:
    """A session, or ``None`` when no database is configured.

    Used by endpoints that must answer even on a cold, unconfigured instance
    (``/config``, health). Everything that reads or writes real data uses the
    required ``SessionDep`` and fails closed.
    """
    try:
        sessionmaker = get_sessionmaker()
    except RuntimeError:
        yield None
        return
    async with sessionmaker() as session:
        yield session


OptionalSessionDep = Annotated[AsyncSession | None, Depends(get_optional_session)]


async def get_token_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenClaims:
    if credentials is None or not credentials.credentials:
        from app.core.errors import UnauthenticatedError

        raise UnauthenticatedError("Please sign in to continue.")
    claims = verify_token(credentials.credentials)
    request.state.token_claims = claims
    return claims


ClaimsDep = Annotated[TokenClaims, Depends(get_token_claims)]


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller: verified claims plus our own profile row."""

    claims: TokenClaims
    profile: Profile

    @property
    def id(self) -> uuid.UUID:
        return self.profile.id

    @property
    def is_admin(self) -> bool:
        return self.profile.role is UserRole.admin

    @property
    def has_phone(self) -> bool:
        return bool(self.profile.phone)


async def get_current_user(
    request: Request,
    claims: ClaimsDep,
    session: SessionDep,
) -> CurrentUser:
    profile = await get_profile(session, claims.sub)
    if profile is None:
        # First authenticated request for this user: create the profile row.
        profile = await ensure_profile(session, claims)
    request.state.user = profile
    return CurrentUser(claims=claims, profile=profile)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser | None:
    """The caller when the request carries a good token, ``None`` otherwise.

    Used by the public quote: a guest gets a price, a signed-in customer additionally
    gets their referral discount and wallet. A bad token is treated as "no token"
    rather than an error, because the route is public either way — and this never
    creates a profile as a side effect of pricing a cart.
    """
    from app.core.errors import UnauthenticatedError

    if credentials is None or not credentials.credentials:
        return None
    try:
        claims = verify_token(credentials.credentials)
    except UnauthenticatedError:
        return None
    profile = await get_profile(session, claims.sub)
    if profile is None:
        return None
    request.state.token_claims = claims
    request.state.user = profile
    return CurrentUser(claims=claims, profile=profile)


OptionalUserDep = Annotated[CurrentUser | None, Depends(get_optional_user)]


async def require_admin(user: CurrentUserDep) -> CurrentUser:
    """Single gate for every admin route. Role comes from ``profiles.role``."""
    if user.profile.role is not UserRole.admin:
        raise ForbiddenError("This area is for the store owner only.", code="admin_only")
    return user


AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
