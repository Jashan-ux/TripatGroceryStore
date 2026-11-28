"""Request dependencies: authentication, the current profile, and admin access.

Authorisation is deny-by-default. Only routers that explicitly depend on
``CurrentUser`` or ``AdminUser`` are protected; everything else is public
read-only catalogue data.

Ownership is enforced inside queries (``user_id`` in the ``WHERE``), never by
fetching a row and comparing afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.core.rate_limit import caller_key, enforce, headers_for
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
    if profile is None or profile.role is not UserRole.customer:
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


async def require_delivery_user(user: CurrentUserDep) -> CurrentUser:
    """Drivers have a separate route surface and never inherit merchant access."""
    if user.profile.role is not UserRole.delivery:
        raise ForbiddenError(
            "This area is for the assigned delivery partner only.", code="delivery_only"
        )
    return user


async def require_customer(user: CurrentUserDep) -> CurrentUser:
    """Customer account and checkout operations are not available to staff roles."""
    if user.profile.role is not UserRole.customer:
        raise ForbiddenError("This action is only available to customers.", code="customer_only")
    return user


AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
DeliveryUserDep = Annotated[CurrentUser, Depends(require_delivery_user)]
CustomerUserDep = Annotated[CurrentUser, Depends(require_customer)]


# --------------------------------------------------------------------------- #
# Rate limits
#
# Attach one of these to the *route* (``dependencies=[Depends(...)]``), not to the
# body, so the counter runs before any of the endpoint's own work — including
# before a validation failure. A wrong referral code has to cost the caller
# something, which only works if failed attempts are counted.
#
# The mechanism lives in ``app.core.rate_limit``; these two wrappers exist because
# *who* is calling differs: a stranger is identified by address, a customer by
# their user id (an address is spoofable, a user id is not).
# --------------------------------------------------------------------------- #
def rate_limit_ip(scope: str) -> Callable[..., Awaitable[None]]:
    """Limit a public route per client address."""

    async def dependency(request: Request, response: Response) -> None:
        decision = await enforce(scope, caller_key(request, prefix="ip"))
        for header, value in headers_for(decision).items():
            response.headers[header] = value

    return dependency


def rate_limit_user(scope: str) -> Callable[..., Awaitable[None]]:
    """Limit an authenticated route per customer."""

    async def dependency(request: Request, response: Response, user: CurrentUserDep) -> None:
        decision = await enforce(scope, f"user:{user.profile.id}")
        for header, value in headers_for(decision).items():
            response.headers[header] = value

    return dependency
