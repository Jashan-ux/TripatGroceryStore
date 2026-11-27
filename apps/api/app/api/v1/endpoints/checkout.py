"""Cart quote and order placement.

`POST /checkout/quote` is public: anybody can price a cart, which is what makes
the cart page's "₹X more to order" honest for a signed-out visitor. Placing the
order needs a signed-in customer with a phone number, an address in a serviceable
pincode and stock that is actually there.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import (
    CurrentUserDep,
    OptionalUserDep,
    SessionDep,
    rate_limit_ip,
    rate_limit_user,
)
from app.schemas.orders import OrderIn, OrderOut, QuoteIn, QuoteOut
from app.services import orders as service

router = APIRouter(tags=["checkout"])

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=64,
        description=(
            "Send the same key when retrying: the API returns the original order "
            "instead of placing a second one."
        ),
    ),
]


@router.post(
    "/checkout/quote",
    response_model=QuoteOut,
    summary="Price a cart (signed in: also the referral discount and wallet)",
    dependencies=[Depends(rate_limit_ip("quote"))],
)
async def quote_cart(
    session: SessionDep, payload: QuoteIn, user: OptionalUserDep = None
) -> QuoteOut:
    return await service.quote(session, payload, profile=user.profile if user else None)


@router.post(
    "/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Place a cash-on-delivery order",
    # Ten orders an hour per customer: far above what a household does, far below
    # what a script needs to tie up the kitchen.
    dependencies=[Depends(rate_limit_user("orders"))],
)
async def place_order(
    request: Request,
    user: CurrentUserDep,
    session: SessionDep,
    payload: OrderIn,
    idempotency_key: IdempotencyKey = None,
) -> OrderOut:
    request.state.idempotent_replay = False
    order = await service.place_order(
        session,
        user.profile,
        payload,
        idempotency_key=idempotency_key,
    )
    return service.order_out(order)
