"""Cart quote and order placement.

`POST /checkout/quote` is public: anybody can price a cart, which is what makes
the cart page's "₹X more to order" honest for a signed-out visitor. Placing the
order needs a signed-in customer with a phone number, an address in a serviceable
pincode and stock that is actually there.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request, status

from app.api.deps import CurrentUserDep, SessionDep
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


@router.post("/checkout/quote", response_model=QuoteOut, summary="Price a cart")
async def quote_cart(session: SessionDep, payload: QuoteIn) -> QuoteOut:
    return await service.quote(session, payload)


@router.post(
    "/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Place a cash-on-delivery order",
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
