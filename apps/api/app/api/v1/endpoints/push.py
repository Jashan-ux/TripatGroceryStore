"""Subscribe or unsubscribe this signed-in browser to web-push messages."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUserDep, SessionDep, rate_limit_user
from app.core.errors import UnavailableError
from app.schemas.push import PushSubscriptionIn, PushSubscriptionOut
from app.services import push as service

router = APIRouter(prefix="/push", tags=["push"])
PushLimit = Annotated[None, Depends(rate_limit_user("push"))]


@router.post(
    "/subscribe",
    response_model=PushSubscriptionOut,
    summary="Enable push on this browser",
)
async def subscribe(
    _: PushLimit,
    user: CurrentUserDep,
    session: SessionDep,
    payload: PushSubscriptionIn,
) -> PushSubscriptionOut:
    if not service.push_is_configured():
        raise UnavailableError("Browser notifications are not configured for this shop yet.")
    await service.register(
        session,
        user.profile,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        expires_at=payload.expiration_time,
    )
    await session.commit()
    return PushSubscriptionOut(enabled=True, message="Notifications are on for this browser.")


@router.delete(
    "/subscribe",
    response_model=PushSubscriptionOut,
    summary="Turn push off on this browser",
)
async def unsubscribe(
    _: PushLimit,
    user: CurrentUserDep,
    session: SessionDep,
    payload: PushSubscriptionIn,
) -> PushSubscriptionOut:
    await service.unregister(session, user.profile, payload.endpoint)
    await session.commit()
    return PushSubscriptionOut(enabled=False, message="Notifications are off for this browser.")
