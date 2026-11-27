"""Database access for addresses, carts quotes and orders.

Two invariants live here rather than in the service layer, because they are
properties of the SQL itself:

* Every address and order query filters by ``profile_id``. Ownership is never
  checked after the fact, so there is no window where another customer's row is
  loaded into memory.
* Stock is taken with a conditional ``UPDATE ... WHERE stock >= :quantity``. The
  row lock makes the check and the decrement atomic; a loser gets ``rowcount 0``
  and nothing to clean up.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import Product, ProductVariant, Profile
from app.models.enums import OrderStatus
from app.models.orders import Address, Order, OrderEvent, OrderItem


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
async def list_addresses(session: AsyncSession, profile_id: uuid.UUID) -> list[Address]:
    stmt = (
        select(Address)
        .where(Address.profile_id == profile_id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return list((await session.scalars(stmt)).all())


async def get_address(
    session: AsyncSession, profile_id: uuid.UUID, address_id: uuid.UUID
) -> Address | None:
    stmt = select(Address).where(Address.id == address_id, Address.profile_id == profile_id)
    return cast("Address | None", await session.scalar(stmt))


async def add_address(session: AsyncSession, address: Address) -> Address:
    session.add(address)
    await session.flush()
    return address


async def clear_other_defaults(
    session: AsyncSession, profile_id: uuid.UUID, keep: uuid.UUID | None = None
) -> None:
    stmt = (
        update(Address)
        .where(Address.profile_id == profile_id, Address.is_default.is_(True))
        .values(is_default=False)
    )
    if keep is not None:
        stmt = stmt.where(Address.id != keep)
    await session.execute(stmt)


async def delete_address(
    session: AsyncSession, profile_id: uuid.UUID, address_id: uuid.UUID
) -> bool:
    stmt = delete(Address).where(Address.id == address_id, Address.profile_id == profile_id)
    result = await session.execute(stmt)
    return bool(result.rowcount)


# --------------------------------------------------------------------------- #
# Catalogue reads used by pricing
# --------------------------------------------------------------------------- #
async def products_for_cart(
    session: AsyncSession, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Product]:
    if not product_ids:
        return {}
    stmt = select(Product).where(Product.id.in_(product_ids), Product.is_active.is_(True))
    rows = list((await session.scalars(stmt)).unique().all())
    return {product.id: product for product in rows}


def unit_stock(product: Product, variant: ProductVariant | None) -> int:
    """A variant is the unit of stock when the product has variants."""
    if variant is not None:
        return variant.stock
    return product.stock


# --------------------------------------------------------------------------- #
# Stock
# --------------------------------------------------------------------------- #
async def take_variant_stock(session: AsyncSession, variant_id: uuid.UUID, quantity: int) -> bool:
    result = await session.execute(
        update(ProductVariant)
        .where(
            ProductVariant.id == variant_id,
            ProductVariant.is_active.is_(True),
            ProductVariant.stock >= quantity,
        )
        .values(stock=ProductVariant.stock - quantity)
    )
    return bool(result.rowcount)


async def take_product_stock(session: AsyncSession, product_id: uuid.UUID, quantity: int) -> bool:
    result = await session.execute(
        update(Product)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
            Product.stock >= quantity,
        )
        .values(stock=Product.stock - quantity)
    )
    return bool(result.rowcount)


async def restore_variant_stock(
    session: AsyncSession, variant_id: uuid.UUID, quantity: int
) -> None:
    await session.execute(
        update(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .values(stock=ProductVariant.stock + quantity)
    )


async def restore_product_stock(
    session: AsyncSession, product_id: uuid.UUID, quantity: int
) -> None:
    await session.execute(
        update(Product).where(Product.id == product_id).values(stock=Product.stock + quantity)
    )


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
async def add_order(session: AsyncSession, order: Order) -> Order:
    session.add(order)
    await session.flush()
    return order


async def add_event(
    session: AsyncSession,
    order_id: uuid.UUID,
    *,
    status: str,
    actor: str,
    note: str = "",
) -> None:
    session.add(OrderEvent(order_id=order_id, status=status, actor=actor, note=note))
    await session.flush()


async def get_order(
    session: AsyncSession, profile_id: uuid.UUID, order_id: uuid.UUID
) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.profile_id == profile_id)
        .execution_options(populate_existing=True)
    )
    return cast("Order | None", await session.scalar(stmt))


async def get_order_by_number(
    session: AsyncSession, profile_id: uuid.UUID, order_number: str
) -> Order | None:
    stmt = select(Order).where(Order.order_number == order_number, Order.profile_id == profile_id)
    return cast("Order | None", await session.scalar(stmt))


async def get_order_by_idempotency(
    session: AsyncSession, profile_id: uuid.UUID, key: str
) -> Order | None:
    stmt = select(Order).where(Order.profile_id == profile_id, Order.idempotency_key == key)
    return cast("Order | None", await session.scalar(stmt))


async def list_orders(
    session: AsyncSession, profile_id: uuid.UUID, *, limit: int, offset: int
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.profile_id == profile_id)
        .order_by(Order.placed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(stmt)).all())


async def count_orders(session: AsyncSession, profile_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(Order).where(Order.profile_id == profile_id)
    return int(await session.scalar(stmt) or 0)


async def get_order_any(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    """Admin read: no profile filter, because the owner owns every order."""
    stmt = select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
    return cast("Order | None", await session.scalar(stmt))


def _admin_filters(
    status: str | None,
    search: str | None,
    order_date: date | None,
    payment_status: str | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if status:
        filters.append(Order.status == status)
    if order_date:
        start = datetime.combine(order_date, time.min, tzinfo=ZoneInfo("Asia/Kolkata"))
        filters.extend((Order.placed_at >= start, Order.placed_at < start + timedelta(days=1)))
    if payment_status:
        filters.append(Order.payment_status == payment_status)
    term = (search or "").strip()
    if term:
        like = f"%{term.lower()}%"
        filters.append(
            or_(
                func.lower(Order.order_number).like(like),
                func.lower(Order.customer_name).like(like),
                Order.customer_phone.like(f"%{term}%"),
            )
        )
    return filters


async def list_all_orders(
    session: AsyncSession,
    *,
    status: str | None = None,
    search: str | None = None,
    order_date: date | None = None,
    payment_status: str | None = None,
    limit: int,
    offset: int,
) -> list[Order]:
    stmt = select(Order).order_by(Order.placed_at.desc()).limit(limit).offset(offset)
    for condition in _admin_filters(status, search, order_date, payment_status):
        stmt = stmt.where(condition)
    return list((await session.scalars(stmt)).all())


async def count_all_orders(
    session: AsyncSession,
    *,
    status: str | None = None,
    search: str | None = None,
    order_date: date | None = None,
    payment_status: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Order)
    for condition in _admin_filters(status, search, order_date, payment_status):
        stmt = stmt.where(condition)
    return int(await session.scalar(stmt) or 0)


async def count_orders_by_status(session: AsyncSession) -> dict[str, int]:
    stmt = select(Order.status, func.count()).group_by(Order.status)
    rows = (await session.execute(stmt)).all()
    counts = {status.value: 0 for status in OrderStatus}
    for status, total in rows:
        counts[str(getattr(status, "value", status))] = int(total)
    return counts


async def order_number_exists(session: AsyncSession, order_number: str) -> bool:
    stmt = select(func.count()).select_from(Order).where(Order.order_number == order_number)
    return bool(await session.scalar(stmt))


async def lock_profile(session: AsyncSession, profile_id: uuid.UUID) -> Profile | None:
    """Serialise one customer's checkouts (two devices, same cart, one order)."""
    stmt = select(Profile).where(Profile.id == profile_id).with_for_update()
    return cast("Profile | None", await session.scalar(stmt))


async def purge_orders(session: AsyncSession, profile_id: uuid.UUID) -> None:
    """Test helper: remove a customer's orders and items."""
    await session.execute(text("DELETE FROM orders WHERE profile_id = :pid"), {"pid": profile_id})
    await session.flush()


__all__ = [
    "Order",
    "OrderEvent",
    "OrderItem",
    "add_address",
    "add_event",
    "add_order",
    "clear_other_defaults",
    "count_orders",
    "delete_address",
    "get_address",
    "get_order",
    "get_order_by_idempotency",
    "get_order_by_number",
    "list_addresses",
    "list_orders",
    "lock_profile",
    "order_number_exists",
    "products_for_cart",
    "restore_product_stock",
    "restore_variant_stock",
    "take_product_stock",
    "take_variant_stock",
    "unit_stock",
]
