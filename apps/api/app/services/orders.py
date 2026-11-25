"""Checkout rules, order placement and cancellation.

Everything a customer can get wrong is decided here, in one place, with the
database as the only source of prices and stock:

* the cart the client sends is a list of ids and quantities — never money;
* `quote()` is the same computation the order would use, so the cart page's
  "₹X short" cannot disagree with what checkout later refuses;
* placing an order takes stock with a conditional update, so the last unit has
  exactly one winner under concurrency;
* cancelling restores exactly the quantity that was taken, once.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.catalogue import Product, Profile, StoreSettings
from app.models.enums import OrderStatus
from app.models.orders import Address, Order, OrderItem
from app.repositories import orders as repo
from app.schemas.orders import (
    AddressIn,
    AddressOut,
    AddressSnapshotOut,
    BlockingIssue,
    CartLineIn,
    OrderEventOut,
    OrderIn,
    OrderItemOut,
    OrderListOut,
    OrderOut,
    OrderSummaryOut,
    QuoteIn,
    QuoteLineOut,
    QuoteOut,
)
from app.services.profiles import normalise_phone
from app.services.settings import get_store_settings

logger = get_logger(__name__)

IssueCode = Literal["out_of_stock", "partially_available", "unavailable"]

ORDER_PREFIX = "MSG"
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # no 0/O/1/I: read out loud safely
MAX_ORDER_ATTEMPTS = 3


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
def address_out(address: Address) -> AddressOut:
    return AddressOut(
        id=address.id,
        label=address.label,
        recipient_name=address.recipient_name,
        phone=address.phone,
        line1=address.line1,
        line2=address.line2,
        landmark=address.landmark,
        pincode=address.pincode,
        city=address.city,
        state=address.state,
        latitude=float(address.latitude) if address.latitude is not None else None,
        longitude=float(address.longitude) if address.longitude is not None else None,
        is_default=address.is_default,
        created_at=address.created_at,
    )


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


async def create_address(session: AsyncSession, profile: Profile, payload: AddressIn) -> Address:
    phone = normalise_phone(payload.phone)
    existing = await repo.list_addresses(session, profile.id)
    address = Address(
        profile_id=profile.id,
        label=_clean_text(payload.label) or "Home",
        recipient_name=_clean_text(payload.recipient_name),
        phone=phone,
        line1=_clean_text(payload.line1),
        line2=_clean_text(payload.line2),
        landmark=_clean_text(payload.landmark),
        pincode=payload.pincode,
        city=_clean_text(payload.city),
        state=_clean_text(payload.state),
        latitude=payload.latitude,
        longitude=payload.longitude,
        # First address is the default whether or not the client said so; the
        # address book can never end up with none.
        is_default=payload.is_default or not existing,
    )
    if address.is_default:
        await repo.clear_other_defaults(session, profile.id)
    await repo.add_address(session, address)
    await session.commit()
    await session.refresh(address)
    logger.info("address_added", profile_id=str(profile.id), address_id=str(address.id))
    return address


async def update_address(
    session: AsyncSession, profile: Profile, address_id: uuid.UUID, payload: AddressIn
) -> Address:
    address = await repo.get_address(session, profile.id, address_id)
    if address is None:
        raise NotFoundError("That address is no longer available.", code="address_not_found")

    address.label = _clean_text(payload.label) or "Home"
    address.recipient_name = _clean_text(payload.recipient_name)
    address.phone = normalise_phone(payload.phone)
    address.line1 = _clean_text(payload.line1)
    address.line2 = _clean_text(payload.line2)
    address.landmark = _clean_text(payload.landmark)
    address.pincode = payload.pincode
    address.city = _clean_text(payload.city)
    address.state = _clean_text(payload.state)
    address.latitude = payload.latitude
    address.longitude = payload.longitude
    if payload.is_default:
        address.is_default = True
        await repo.clear_other_defaults(session, profile.id, keep=address.id)
    await session.commit()
    await session.refresh(address)
    return address


async def delete_address(session: AsyncSession, profile: Profile, address_id: uuid.UUID) -> None:
    address = await repo.get_address(session, profile.id, address_id)
    if address is None:
        raise NotFoundError("That address is no longer available.", code="address_not_found")
    was_default = address.is_default
    await repo.delete_address(session, profile.id, address_id)
    await session.flush()
    if was_default:
        remaining = await repo.list_addresses(session, profile.id)
        if remaining:
            remaining[0].is_default = True
    await session.commit()


def address_snapshot(address: Address) -> dict[str, str]:
    """The immutable copy stored on the order."""
    return {
        "label": address.label,
        "recipient_name": address.recipient_name,
        "phone": address.phone,
        "line1": address.line1,
        "line2": address.line2,
        "landmark": address.landmark,
        "pincode": address.pincode,
        "city": address.city,
        "state": address.state,
    }


# --------------------------------------------------------------------------- #
# Pricing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PricedLine:
    product: Product
    unit_price_paise: int
    mrp_paise: int
    quantity: int
    available_stock: int
    variant_id: uuid.UUID | None
    variant_label: str
    issue: str | None

    @property
    def billable(self) -> bool:
        return self.issue is None

    @property
    def line_total_paise(self) -> int:
        return self.unit_price_paise * self.quantity if self.billable else 0


def _deliver_by(settings: StoreSettings, *, today: date | None = None) -> date:
    start = today or datetime.now(tz=UTC).date()
    return start + timedelta(days=max(1, settings.default_delivery_days))


def price_lines(products: dict[uuid.UUID, Product], items: list[CartLineIn]) -> list[PricedLine]:
    """Price the cart from the database. The client's numbers are never used."""
    priced: list[PricedLine] = []
    for item in items:
        product = products.get(item.product_id)
        if product is None:
            priced.append(_missing_line(item))
            continue

        variant = None
        if item.variant_id is not None:
            variant = next(
                (entry for entry in product.variants if entry.id == item.variant_id), None
            )
            if variant is None or not variant.is_active:
                priced.append(_missing_line(item))
                continue

        stock = repo.unit_stock(product, variant)
        unit_price = variant.price_paise if variant is not None else product.price_paise
        mrp = variant.mrp_paise if variant is not None else product.mrp_paise
        issue: str | None = None
        if stock <= 0:
            issue = "out_of_stock"
        elif stock < item.quantity:
            issue = "partially_available"

        priced.append(
            PricedLine(
                product=product,
                unit_price_paise=unit_price,
                mrp_paise=mrp,
                quantity=item.quantity,
                available_stock=stock,
                variant_id=variant.id if variant is not None else None,
                variant_label=variant.label if variant is not None else "",
                issue=issue,
            )
        )
    return priced


def _missing_line(item: CartLineIn) -> PricedLine:
    """A cart entry whose product or variant is gone: keep the line, flag it."""
    placeholder = Product()
    placeholder.id = item.product_id
    placeholder.name = "No longer available"
    placeholder.slug = ""
    placeholder.unit_label = ""
    placeholder.price_paise = 0
    placeholder.mrp_paise = 0
    return PricedLine(
        product=placeholder,
        unit_price_paise=0,
        mrp_paise=0,
        quantity=item.quantity,
        available_stock=0,
        variant_id=item.variant_id,
        variant_label="",
        issue="unavailable",
    )


def _quote_line_out(line: PricedLine) -> QuoteLineOut:
    image = line.product.images[0] if line.product.images else ""
    return QuoteLineOut(
        product_id=line.product.id,
        variant_id=line.variant_id,
        slug=line.product.slug,
        name=line.product.name,
        unit_label=line.product.unit_label,
        variant_label=line.variant_label,
        image_url=image,
        unit_price_paise=line.unit_price_paise,
        mrp_paise=line.mrp_paise,
        quantity=line.quantity,
        line_total_paise=line.line_total_paise,
        available_stock=line.available_stock,
        in_stock=line.available_stock > 0,
        issue=cast(IssueCode, line.issue),
    )


async def quote(session: AsyncSession, payload: QuoteIn) -> QuoteOut:
    settings = await get_store_settings(session)
    product_ids = list({item.product_id for item in payload.items})
    products = await repo.products_for_cart(session, product_ids)
    lines = price_lines(products, payload.items)

    subtotal = sum(line.line_total_paise for line in lines)
    item_count = sum(line.quantity for line in lines if line.billable)
    delivery_fee = 0
    discount = 0
    total = subtotal + delivery_fee - discount

    issues: list[BlockingIssue] = []
    unavailable = [line.product.name for line in lines if not line.billable]
    if unavailable:
        issues.append(
            BlockingIssue(
                code="stock",
                message=(
                    "Some items in your cart are not available in that quantity. "
                    "Adjust the quantities to continue."
                ),
                details={"items": unavailable},
            )
        )
    shortfall = max(0, settings.minimum_order_paise - subtotal)
    if shortfall:
        issues.append(
            BlockingIssue(
                code="minimum_order",
                message=(
                    f"Minimum order is ₹{settings.minimum_order_paise // 100}. "
                    f"Add ₹{shortfall // 100} more to continue."
                ),
                details={
                    "shortfall_paise": shortfall,
                    "minimum_order_paise": settings.minimum_order_paise,
                },
            )
        )
    serviceable: bool | None = None
    if payload.pincode is not None:
        serviceable = payload.pincode in settings.serviceable_pincodes
        if not serviceable:
            issues.append(
                BlockingIssue(
                    code="pincode",
                    message=(
                        "We do not deliver to that pincode yet. "
                        "Call the store and we will see what we can do."
                    ),
                    details={"pincode": payload.pincode},
                )
            )

    return QuoteOut(
        lines=[_quote_line_out(line) for line in lines],
        item_count=item_count,
        subtotal_paise=subtotal,
        delivery_fee_paise=delivery_fee,
        discount_paise=discount,
        total_paise=total,
        minimum_order_paise=settings.minimum_order_paise,
        shortfall_paise=shortfall,
        delivery_days=max(1, settings.default_delivery_days),
        deliver_by=_deliver_by(settings),
        pincode=payload.pincode,
        pincode_serviceable=serviceable,
        blocking_issues=issues,
        # A pincode only blocks when the customer has chosen one; the cart page
        # gets its answer before checkout asks for an address.
        can_checkout=subtotal > 0
        and shortfall == 0
        and not unavailable
        and serviceable is not False,
    )


# --------------------------------------------------------------------------- #
# Order numbers
# --------------------------------------------------------------------------- #
def generate_order_number(*, today: date | None = None) -> str:
    stamp = (today or datetime.now(tz=UTC).date()).strftime("%y%m%d")
    suffix = "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
    return f"{ORDER_PREFIX}-{stamp}-{suffix}"


async def _unique_order_number(session: AsyncSession) -> str:
    for _ in range(MAX_ORDER_ATTEMPTS):
        candidate = generate_order_number()
        if not await repo.order_number_exists(session, candidate):
            return candidate
    raise ConflictError("Could not allocate an order number. Please try again.")


# --------------------------------------------------------------------------- #
# Placing an order
# --------------------------------------------------------------------------- #
async def place_order(
    session: AsyncSession,
    profile: Profile,
    payload: OrderIn,
    *,
    idempotency_key: str | None,
) -> Order:
    # One checkout at a time per customer: double taps and two tabs collapse into
    # one order even before the idempotency key is considered.
    await repo.lock_profile(session, profile.id)

    if idempotency_key:
        existing = await repo.get_order_by_idempotency(session, profile.id, idempotency_key)
        if existing is not None:
            # Commit releases the profile lock; the session is configured with
            # expire_on_commit=False, so the loaded order stays readable (a
            # rollback would expire it and make serialisation do lazy IO).
            await session.commit()
            logger.info("order_replayed", order_id=str(existing.id))
            return existing

    if not profile.phone:
        raise ConflictError(
            "Add your mobile number before placing an order — the delivery partner "
            "calls before arriving.",
            code="phone_required",
        )

    address = await repo.get_address(session, profile.id, payload.address_id)
    if address is None:
        raise NotFoundError("Choose a delivery address.", code="address_not_found")

    settings = await get_store_settings(session)
    if address.pincode not in settings.serviceable_pincodes:
        raise ValidationError(
            "We do not deliver to that pincode yet.",
            code="pincode_not_serviceable",
            details={"field": "pincode", "pincode": address.pincode},
        )

    product_ids = list({item.product_id for item in payload.items})
    products = await repo.products_for_cart(session, product_ids)
    lines = price_lines(products, payload.items)
    if not lines:
        raise ValidationError("Your cart is empty.", code="empty_cart")

    unavailable = [line.product.name for line in lines if not line.billable]
    if unavailable:
        raise ConflictError(
            "Some items are no longer available in that quantity.",
            code="insufficient_stock",
            details={"items": unavailable},
        )

    subtotal = sum(line.line_total_paise for line in lines)
    if subtotal < settings.minimum_order_paise:
        shortfall = settings.minimum_order_paise - subtotal
        raise ValidationError(
            f"Minimum order is ₹{settings.minimum_order_paise // 100}.",
            code="minimum_order_not_met",
            details={"shortfall_paise": shortfall},
        )

    order_number = await _unique_order_number(session)
    delivery_days = max(1, settings.default_delivery_days)
    order = Order(
        order_number=order_number,
        profile_id=profile.id,
        subtotal_paise=subtotal,
        delivery_fee_paise=0,
        discount_paise=0,
        total_paise=subtotal,
        item_count=sum(line.quantity for line in lines),
        customer_name=profile.name or address.recipient_name,
        customer_phone=profile.phone,
        address_snapshot=address_snapshot(address),
        delivery_days=delivery_days,
        deliver_by=_deliver_by(settings),
        customer_note=payload.customer_note,
        idempotency_key=idempotency_key,
    )

    for index, line in enumerate(lines):
        order.items.append(
            OrderItem(
                product_id=line.product.id,
                variant_id=line.variant_id,
                name=line.product.name,
                unit_label=line.product.unit_label,
                variant_label=line.variant_label,
                image_url=line.product.images[0] if line.product.images else "",
                unit_price_paise=line.unit_price_paise,
                mrp_paise=line.mrp_paise,
                quantity=line.quantity,
                line_total_paise=line.line_total_paise,
                sort_order=index,
            )
        )

    try:
        await repo.add_order(session, order)
    except IntegrityError:
        # Either the order number or the idempotency key collided. Both are
        # recoverable: a replay returns the original order.
        await session.rollback()
        if idempotency_key:
            replayed = await repo.get_order_by_idempotency(session, profile.id, idempotency_key)
            if replayed is not None:
                return replayed
        raise ConflictError(
            "Could not place that order. Please try again.", code="order_conflict"
        ) from None

    taken: list[tuple[uuid.UUID | None, uuid.UUID, int, str]] = []
    for line in lines:
        if line.variant_id is not None:
            ok = await repo.take_variant_stock(session, line.variant_id, line.quantity)
        else:
            ok = await repo.take_product_stock(session, line.product.id, line.quantity)
        if not ok:
            # Read what the message needs *before* the rollback expires the rows.
            name = line.product.name
            await session.rollback()
            raise ConflictError(
                f"Only a few left of {name}. Please adjust your cart.",
                code="insufficient_stock",
                details={"items": [name]},
            )
        taken.append((line.variant_id, line.product.id, line.quantity, line.product.name))

    await repo.add_event(
        session,
        order.id,
        status=OrderStatus.processing.value,
        actor="customer",
        note="Order placed",
    )
    await session.commit()
    await session.refresh(order)
    logger.info(
        "order_placed",
        order_id=str(order.id),
        order_number=order.order_number,
        total_paise=order.total_paise,
        items=len(lines),
    )
    return order


async def cancel_order(
    session: AsyncSession, profile: Profile, order_id: uuid.UUID, reason: str
) -> Order:
    order = await repo.get_order(session, profile.id, order_id)
    if order is None:
        raise NotFoundError("That order is not yours.", code="order_not_found")
    if order.status is not OrderStatus.processing:
        raise ConflictError(
            "This order has already left the shop, so it can no longer be cancelled here. "
            "Please call the store.",
            code="order_not_cancellable",
            details={"status": order.status.value},
        )

    for item in order.items:
        if item.variant_id is not None:
            await repo.restore_variant_stock(session, item.variant_id, item.quantity)
        else:
            await repo.restore_product_stock(session, item.product_id, item.quantity)

    order.status = OrderStatus.cancelled
    order.cancelled_at = datetime.now(tz=UTC)
    order.cancelled_reason = reason
    await repo.add_event(
        session,
        order.id,
        status=OrderStatus.cancelled.value,
        actor="customer",
        note=reason or "Cancelled by the customer",
    )
    await session.commit()
    await session.refresh(order)
    logger.info("order_cancelled", order_id=str(order.id), order_number=order.order_number)
    return order


# --------------------------------------------------------------------------- #
# Reading orders
# --------------------------------------------------------------------------- #
def order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        payment_method=order.payment_method.value,
        payment_status=order.payment_status.value,
        subtotal_paise=order.subtotal_paise,
        delivery_fee_paise=order.delivery_fee_paise,
        discount_paise=order.discount_paise,
        total_paise=order.total_paise,
        item_count=order.item_count,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_note=order.customer_note,
        address=AddressSnapshotOut.model_validate(order.address_snapshot),
        delivery_days=order.delivery_days,
        deliver_by=order.deliver_by,
        placed_at=order.placed_at,
        cancelled_at=order.cancelled_at,
        cancelled_reason=order.cancelled_reason,
        items=[
            OrderItemOut(
                id=item.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                name=item.name,
                unit_label=item.unit_label,
                variant_label=item.variant_label,
                image_url=item.image_url,
                unit_price_paise=item.unit_price_paise,
                mrp_paise=item.mrp_paise,
                quantity=item.quantity,
                line_total_paise=item.line_total_paise,
            )
            for item in order.items
        ],
        events=[
            OrderEventOut(
                status=event.status.value,
                actor=event.actor,
                note=event.note,
                created_at=event.created_at,
            )
            for event in order.events
        ],
    )


def order_summary(order: Order) -> OrderSummaryOut:
    first = order.items[0] if order.items else None
    return OrderSummaryOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        payment_status=order.payment_status.value,
        total_paise=order.total_paise,
        item_count=order.item_count,
        placed_at=order.placed_at,
        deliver_by=order.deliver_by,
        first_item_name=first.name if first is not None else "",
        first_item_image_url=first.image_url if first is not None else "",
    )


async def list_my_orders(
    session: AsyncSession, profile: Profile, *, page: int, page_size: int
) -> OrderListOut:
    total = await repo.count_orders(session, profile.id)
    orders = await repo.list_orders(
        session, profile.id, limit=page_size, offset=(page - 1) * page_size
    )
    return OrderListOut(
        items=[order_summary(order) for order in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=-(-total // page_size) if page_size else 0,
    )


async def get_my_order(session: AsyncSession, profile: Profile, order_id: uuid.UUID) -> Order:
    order = await repo.get_order(session, profile.id, order_id)
    if order is None:
        raise NotFoundError("That order is not yours.", code="order_not_found")
    return order


async def get_my_order_by_number(
    session: AsyncSession, profile: Profile, order_number: str
) -> Order:
    order = await repo.get_order_by_number(session, profile.id, order_number)
    if order is None:
        raise NotFoundError("That order is not yours.", code="order_not_found")
    return order
