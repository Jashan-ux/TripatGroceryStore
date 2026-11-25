"""Public feedback: anyone can write to the shop, signed in or not."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import OptionalSessionDep, OptionalUserDep
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


# Rate limiting is not applied here yet: the limiter exists in ``app.core.rate_limit``
# but the app does not install it (see docs/ACCEPTANCE_REPORT.md, S-06). Wiring a
# decorator that the app never enforces would be a promise the code cannot keep.
