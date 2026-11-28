"""Queries and transitions for the single-worker delivery workspace."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import OrderStatus, UserRole
from app.models.orders import Order
from app.repositories import orders as order_repo
from app.schemas.admin_orders import AdminOrderStatusIn
from app.schemas.delivery import (
    DeliveryCandidateOut,
    DeliveryOrderItemOut,
    DeliveryOrderListOut,
    DeliveryOrderOut,
    DeliveryProfileOut,
)
from app.services import admin_orders, audit
from app.services.settings import get_store_settings

ACTIVE_DELIVERY_STATUSES = (OrderStatus.shipped, OrderStatus.out_for_delivery)


async def list_delivery_profiles(session: AsyncSession) -> list[DeliveryProfileOut]:
    rows = await session.scalars(
        select(Profile).where(Profile.role == UserRole.delivery).order_by(Profile.name, Profile.id)
    )
    return [DeliveryProfileOut(id=row.id, name=row.name, phone=row.phone) for row in rows]


async def list_candidates(session: AsyncSession, query: str = "") -> list[DeliveryCandidateOut]:
    stmt = select(Profile).where(Profile.role == UserRole.customer)
    term = query.strip()
    if term:
        pattern = f"%{term.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Profile.name).ilike(pattern),
                func.lower(Profile.email).ilike(pattern),
                Profile.phone.ilike(f"%{term}%"),
            )
        )
    rows = await session.scalars(stmt.order_by(Profile.name, Profile.id).limit(50))
    return [
        DeliveryCandidateOut(id=row.id, name=row.name, phone=row.phone, email=row.email)
        for row in rows
    ]


async def promote_profile(
    session: AsyncSession, profile_id: uuid.UUID, *, actor: Profile
) -> DeliveryProfileOut:
    profile = await session.scalar(
        select(Profile).where(Profile.id == profile_id).with_for_update()
    )
    if profile is None:
        raise NotFoundError("No customer profile with that id.", code="profile_not_found")
    if profile.role is not UserRole.customer:
        raise ConflictError(
            "Only a customer profile can be enabled for delivery.", code="invalid_profile_role"
        )
    profile.role = UserRole.delivery
    await audit.record(
        session,
        actor=actor,
        action="profile.delivery_enabled",
        entity="profile",
        entity_id=profile.id,
        summary=profile.name,
        before={"role": "customer"},
        after={"role": "delivery"},
    )
    await session.commit()
    return DeliveryProfileOut(id=profile.id, name=profile.name, phone=profile.phone)


def driver_order_out(order: Order) -> DeliveryOrderOut:
    return DeliveryOrderOut(
        id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        payment_method=order.payment_method.value,
        payment_status=order.payment_status.value,
        total_paise=order.total_paise,
        item_count=order.item_count,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        address=order.address_snapshot or {},
        items=[
            DeliveryOrderItemOut(
                name=item.name,
                unit_label=item.unit_label,
                variant_label=item.variant_label,
                quantity=item.quantity,
                line_total_paise=item.line_total_paise,
            )
            for item in order.items
        ],
        out_for_delivery_at=order.out_for_delivery_at,
        delivered_at=order.delivered_at,
    )


async def list_assigned_orders(session: AsyncSession, driver_id: uuid.UUID) -> DeliveryOrderListOut:
    rows = list(
        (
            await session.scalars(
                select(Order)
                .where(
                    Order.assigned_to == driver_id,
                    Order.status.in_(ACTIVE_DELIVERY_STATUSES),
                )
                .order_by(Order.placed_at.asc())
            )
        ).all()
    )
    return DeliveryOrderListOut(items=[driver_order_out(row) for row in rows], total=len(rows))


async def get_assigned_order(
    session: AsyncSession, driver_id: uuid.UUID, order_id: uuid.UUID, *, lock: bool = False
) -> Order:
    stmt = select(Order).where(Order.id == order_id, Order.assigned_to == driver_id)
    if lock:
        stmt = stmt.with_for_update()
    order = await session.scalar(stmt.execution_options(populate_existing=True))
    if order is None:
        # Avoid confirming that an unassigned order exists.
        raise NotFoundError(
            "That assigned delivery is not available.", code="delivery_order_not_found"
        )
    return order


async def update_delivery_status(
    session: AsyncSession, driver: Profile, order_id: uuid.UUID, *, delivered: bool
) -> tuple[Order, bool]:
    order = await get_assigned_order(session, driver.id, order_id, lock=True)
    target = OrderStatus.delivered if delivered else OrderStatus.out_for_delivery
    if order.status is target:
        # Retries after a network timeout are safe and do not duplicate events,
        # email, push, wallet credits or timestamps.
        return order, False
    expected = OrderStatus.out_for_delivery if delivered else OrderStatus.shipped
    if order.status is not expected:
        raise ConflictError(
            f"This delivery is {order.status.value.replace('_', ' ')} and cannot be marked "
            f"{target.value.replace('_', ' ')}.",
            code="invalid_status_transition",
            details={"status": order.status.value, "requested": target.value},
        )
    updated = await admin_orders.transition(
        session,
        order,
        AdminOrderStatusIn(status=target.value),
        actor=driver,
    )
    return updated, True


async def assign_order(
    session: AsyncSession,
    order: Order,
    *,
    driver_id: uuid.UUID | None,
    actor: Profile,
) -> Order:
    if order.status in admin_orders.FINISHED_STATUSES:
        raise ConflictError(
            "A finished order cannot be assigned for delivery.", code="order_not_editable"
        )
    driver = None
    if driver_id is not None:
        driver = await session.get(Profile, driver_id)
        if driver is None or driver.role is not UserRole.delivery:
            raise ValidationError(
                "Choose an existing delivery profile.",
                code="invalid_delivery_profile",
                details={"field": "profile_id"},
            )
    old_driver_id = order.assigned_to
    if old_driver_id == driver_id:
        return order
    order.assigned_to = driver_id
    order.delivery_profile = driver
    await order_repo.add_event(
        session,
        order.id,
        status=order.status.value,
        actor="admin",
        note=(
            f"Delivery assigned to {driver.name} by {actor.name}"
            if driver
            else f"Delivery assignment cleared by {actor.name}"
        ),
    )
    await session.commit()
    await session.refresh(order)
    return order


async def assign_default_driver(session: AsyncSession, order: Order, *, actor: Profile) -> Order:
    settings = await get_store_settings(session)
    driver_id = settings.default_delivery_profile_id
    if driver_id is None:
        raise ConflictError(
            "Set a default delivery person in Settings first.", code="default_driver_missing"
        )
    return await assign_order(session, order, driver_id=driver_id, actor=actor)


async def read_default_driver_id(session: AsyncSession) -> uuid.UUID | None:
    settings: StoreSettings = await get_store_settings(session)
    return settings.default_delivery_profile_id
