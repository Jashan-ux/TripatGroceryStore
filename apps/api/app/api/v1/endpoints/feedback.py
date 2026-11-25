"""Public feedback: anyone can write to the shop, signed in or not."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import OptionalSessionDep, OptionalUserDep, rate_limit_ip
from app.core.errors import UnavailableError
from app.schemas.admin_ops import FeedbackIn, FeedbackOut
from app.services import feedback as service
from app.services.settings import get_store_settings

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send the shop a message",
    # Five messages an hour from one address: a person writes once or twice, so
    # the ceiling only ever catches a script.
    dependencies=[Depends(rate_limit_ip("feedback"))],
)
async def send_feedback(
    payload: FeedbackIn,
    session: OptionalSessionDep,
    user: OptionalUserDep,
) -> FeedbackOut:
    if session is None:  # pragma: no cover - only on an unconfigured instance
        raise UnavailableError("The shop is not ready to take messages yet.")
    settings = await get_store_settings(session)
    row = await service.submit(
        session, payload=payload, user=user.profile if user else None, settings=settings
    )
    await session.commit()
    return row
