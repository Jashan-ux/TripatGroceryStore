"""What the shop tells people, and where they read it.

Every message is written by a function here rather than inline in the order
service, for one reason: the wording is product copy, and it must not drift
between the bell, the email and the order page. Each function takes the order (and
store settings when it needs them) and returns rows; the caller commits, so a
notification can never outlive the fact it describes.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.catalogue import Profile, StoreSettings
from app.models.enums import NotificationKind, OrderStatus
from app.models.notifications import Notification
from app.models.orders import Order
from app.repositories import notifications as repo
from app.schemas.notifications import NotificationListOut, NotificationOut
from app.services.email import queue as queue_email
from app.services.format import day, day_count, items_phrase, rupees

logger = get_logger(__name__)

STATUS_COPY: dict[OrderStatus, tuple[str, str]] = {
    OrderStatus.processing: ("Order received", "The store has received your order."),
    OrderStatus.accepted: ("Order accepted", "The store has accepted your order."),
    OrderStatus.packing: ("Being packed", "The store is packing your order."),
    OrderStatus.shipped: ("Packed and shipped", "Your order has left the shop."),
    OrderStatus.out_for_delivery: (
        "Out for delivery",
        "Our delivery partner is on the way. Keep the cash ready.",
    ),
    OrderStatus.delivered: (
        "Delivered",
        "Your order has been delivered. Thank you for shopping with us.",
    ),
    OrderStatus.cancelled: ("Order cancelled", "This order has been cancelled."),
    OrderStatus.returned: ("Return received", "We have taken the return back."),
}


def notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        kind=notification.kind.value,
        title=notification.title,
        body=notification.body,
        href=notification.href,
        order_id=notification.order_id,
        read=notification.read_at is not None,
        created_at=notification.created_at,
    )


def _add(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    href: str,
    order_id: uuid.UUID | None = None,
) -> Notification:
    return Notification(
        profile_id=profile_id,
        kind=kind,
        title=title[:140],
        body=body,
        href=href,
        order_id=order_id,
    )


async def _customer_email(
    session: AsyncSession,
    *,
    profile: Profile,
    order: Order,
    subject: str,
    lines: list[str],
    settings: StoreSettings,
    dedupe_suffix: str,
) -> None:
    """Queue the email twin of a notification, signed with the shop's details."""
    if not profile.email:
        return
    paid = [f"Paid from your wallet: {rupees(order.wallet_paise)}"] if order.wallet_paise else []
    body = "\n".join(
        [
            *lines,
            "",
            f"Order: {order.order_number}",
            *paid,
            f"Total: {rupees(order.total_paise)} (cash on delivery)",
            f"Delivering to: {order.customer_name}, {order.address_snapshot.get('line1', '')}, "
            f"{order.address_snapshot.get('city', '')} {order.address_snapshot.get('pincode', '')}",
            "",
            f"{settings.store_name} · {settings.store_phone}",
            settings.store_address,
        ]
    )
    await queue_email(
        session,
        to=profile.email,
        subject=subject,
        body=body,
        dedupe_key=f"order:{order.id}:{dedupe_suffix}:{profile.email.lower()}",
    )


async def _simple_email(
    session: AsyncSession,
    *,
    profile: Profile,
    subject: str,
    lines: list[str],
    settings: StoreSettings,
    dedupe_key: str,
    anchor: str,
) -> None:
    """The email twin of a message that is not about an order's status.

    ``dedupe_key`` names the fact being told ("referral:<id>:bonus"), so a replay of
    the same fact can never post a second email.
    """
    if not profile.email:
        return
    body = "\n".join(
        [
            f"Hello {profile.name or 'there'},",
            "",
            *lines,
            "",
            anchor,
            "",
            f"{settings.store_name} · {settings.store_phone}",
            settings.store_address,
        ]
    )
    await queue_email(
        session,
        to=profile.email,
        subject=subject,
        body=body,
        dedupe_key=dedupe_key,
    )


# --------------------------------------------------------------------------- #
# Customer: order placed
# --------------------------------------------------------------------------- #
async def announce_order_placed(
    session: AsyncSession,
    order: Order,
    profile: Profile,
    settings: StoreSettings,
) -> None:
    eta = f" We will deliver by {day(order.deliver_by)}." if order.deliver_by else ""
    session.add(
        _add(
            session,
            profile_id=profile.id,
            kind=NotificationKind.order_placed,
            title=f"Order {order.order_number} confirmed",
            body=(
                f"Thank you! {items_phrase(order.item_count)} · {rupees(order.total_paise)}, "
                f"cash on delivery."
                + (
                    f" {rupees(order.wallet_paise)} already paid from your wallet."
                    if order.wallet_paise
                    else ""
                )
                + eta
            ),
            href=f"/orders/{order.id}",
            order_id=order.id,
        )
    )
    await _customer_email(
        session,
        profile=profile,
        order=order,
        subject=f"Your {settings.store_name} order {order.order_number} is confirmed",
        lines=[
            f"Thank you, {order.customer_name or 'friend'}.",
            "",
            f"{items_phrase(order.item_count)} · {rupees(order.total_paise)} "
            "to pay in cash on delivery.",
            *(
                [f"{rupees(order.wallet_paise)} of that is already paid from your wallet."]
                if order.wallet_paise
                else []
            ),
            *(f"  {item.quantity} × {item.name}" for item in order.items),
            "",
            f"We will deliver by {day(order.deliver_by)}." if order.deliver_by else "",
        ],
        settings=settings,
        dedupe_suffix="placed",
    )


# --------------------------------------------------------------------------- #
# Owner: a new order
# --------------------------------------------------------------------------- #
async def announce_new_order(session: AsyncSession, order: Order, settings: StoreSettings) -> None:
    owners = await repo.list_admin_profiles(session)
    for owner in owners:
        session.add(
            _add(
                session,
                profile_id=owner.id,
                kind=NotificationKind.new_order,
                title=f"New order {order.order_number}",
                body=(
                    f"{order.customer_name or 'A customer'} · {items_phrase(order.item_count)} · "
                    f"{rupees(order.total_paise)} · {order.address_snapshot.get('pincode', '')}"
                ),
                href="/admin/orders",
                order_id=order.id,
            )
        )
        if owner.email:
            await queue_email(
                session,
                to=owner.email,
                subject=f"New order {order.order_number} · {rupees(order.total_paise)}",
                body="\n".join(
                    [
                        f"{order.customer_name or 'A customer'} just ordered.",
                        "",
                        f"Phone: {order.customer_phone}",
                        *(f"  {item.quantity} × {item.name}" for item in order.items),
                        "",
                        f"Total: {rupees(order.total_paise)} (cash on delivery)",
                        f"Deliver by: {day(order.deliver_by)}",
                        f"Pincode: {order.address_snapshot.get('pincode', '')}",
                        "",
                        "Open the shop → Orders to move it along.",
                        f"{settings.store_name}",
                    ]
                ),
                dedupe_key=f"order:{order.id}:new:{owner.email.lower()}",
            )


# --------------------------------------------------------------------------- #
# Customer: status moved (by the shop, or cancelled by either side)
# --------------------------------------------------------------------------- #
async def announce_status_change(
    session: AsyncSession,
    order: Order,
    profile: Profile,
    settings: StoreSettings,
    *,
    note: str = "",
) -> None:
    headline, detail = STATUS_COPY.get(order.status, ("Order updated", ""))
    cancelled = order.status is OrderStatus.cancelled
    body = note or detail
    session.add(
        _add(
            session,
            profile_id=profile.id,
            kind=(NotificationKind.order_cancelled if cancelled else NotificationKind.order_status),
            title=f"{order.order_number}: {headline}",
            body=body,
            href=f"/orders/{order.id}",
            order_id=order.id,
        )
    )
    await _customer_email(
        session,
        profile=profile,
        order=order,
        subject=f"{order.order_number}: {headline}",
        lines=[f"Hello {order.customer_name or 'there'},", "", body],
        settings=settings,
        dedupe_suffix=f"status-{order.status.value}",
    )


# --------------------------------------------------------------------------- #
# Owner: the customer cancelled
# --------------------------------------------------------------------------- #
async def announce_cancellation_to_shop(session: AsyncSession, order: Order) -> None:
    """A cancel means stock came back and a slot freed up — the counter must know."""
    for owner in await repo.list_admin_profiles(session):
        session.add(
            _add(
                session,
                profile_id=owner.id,
                kind=NotificationKind.order_cancelled,
                title=f"{order.order_number} cancelled by the customer",
                body=(
                    f"{order.customer_name or 'The customer'} cancelled "
                    f"{items_phrase(order.item_count)} · {rupees(order.total_paise)}. "
                    "The stock is back on the shelf."
                ),
                href="/admin/orders",
                order_id=order.id,
            )
        )


# --------------------------------------------------------------------------- #
# Customer: the shop changed the delivery promise
# --------------------------------------------------------------------------- #
async def announce_delivery_change(
    session: AsyncSession,
    order: Order,
    profile: Profile,
    settings: StoreSettings,
) -> None:
    """The order itself is unchanged; only the date the customer was promised moved."""
    title = f"{order.order_number}: Delivery in {day_count(order.delivery_days)}"
    session.add(
        _add(
            session,
            profile_id=profile.id,
            kind=NotificationKind.system,
            title=title,
            body=f"The shop has updated your delivery estimate to {day(order.deliver_by)}.",
            href=f"/orders/{order.id}",
            order_id=order.id,
        )
    )
    await _customer_email(
        session,
        profile=profile,
        order=order,
        subject=title,
        lines=[
            f"Hello {order.customer_name or 'there'},",
            "",
            f"We have updated the delivery estimate for {order.order_number} "
            f"to {day(order.deliver_by)} ({day_count(order.delivery_days)}).",
            "If that does not suit you, call the shop and we will sort it out.",
        ],
        settings=settings,
        dedupe_suffix=f"delivery-{order.delivery_days}-{order.deliver_by}",
    )


# --------------------------------------------------------------------------- #
# Rewards: money earned, badges, cards and returns
# --------------------------------------------------------------------------- #
async def announce_referral_bonus(
    session: AsyncSession,
    referrer: Profile,
    *,
    friend_name: str,
    amount_paise: int,
    referral_id: uuid.UUID,
    settings: StoreSettings,
) -> None:
    title = f"{rupees(amount_paise)} added to your wallet"
    body = f"{friend_name} got their first order delivered. Thank you for sending them our way."
    session.add(
        _add(
            session,
            profile_id=referrer.id,
            kind=NotificationKind.system,
            title=title,
            body=body,
            href="/rewards",
        )
    )
    await _simple_email(
        session,
        profile=referrer,
        subject=title,
        lines=[body, "Your wallet balance is ready to spend on your next order."],
        settings=settings,
        dedupe_key=f"referral:{referral_id}:bonus",
        anchor="Open Rewards to see your wallet and invite another friend.",
    )


async def announce_tier_upgrade(
    session: AsyncSession,
    profile: Profile,
    *,
    tier_label: str,
    spend_paise: int,
    settings: StoreSettings,
) -> None:
    title = f"You are now a {tier_label}"
    body = f"That is {rupees(spend_paise)} of delivered orders. Thank you for shopping with us."
    session.add(
        _add(
            session,
            profile_id=profile.id,
            kind=NotificationKind.system,
            title=title,
            body=body,
            href="/rewards",
        )
    )
    await _simple_email(
        session,
        profile=profile,
        subject=f"{settings.store_name}: {title}",
        lines=[body],
        settings=settings,
        dedupe_key=f"tier:{profile.id}:{spend_paise}:{tier_label}",
        anchor="Open Rewards to see how far the next badge is.",
    )


async def announce_scratch_ready(
    session: AsyncSession,
    profile: Profile,
    *,
    card_id: uuid.UUID,
    order_number: str,
) -> None:
    session.add(
        _add(
            session,
            profile_id=profile.id,
            kind=NotificationKind.system,
            title="A scratch card is ready",
            body=(
                f"Order {order_number} was delivered, so your scratch card is unlocked. "
                "Rub it off to see what you won."
            ),
            href="/rewards",
        )
    )
    logger.debug("scratch_ready_notified", card_id=str(card_id), profile_id=str(profile.id))


async def announce_return_requested(
    session: AsyncSession, *, order_number: str, return_id: uuid.UUID, refund_paise: int
) -> None:
    """The counter needs to know a return is waiting for a decision."""
    for owner in await repo.list_admin_profiles(session):
        session.add(
            _add(
                session,
                profile_id=owner.id,
                kind=NotificationKind.system,
                title=f"Return requested for {order_number}",
                body=f"{rupees(refund_paise)} is waiting on your decision.",
                href="/admin/returns",
            )
        )


async def announce_return_update(
    session: AsyncSession,
    profile: Profile,
    *,
    order_number: str,
    status: str,
    refund_paise: int,
    note: str,
    return_id: uuid.UUID,
    settings: StoreSettings,
) -> None:
    headline, detail = {
        "approved": (
            "Return approved",
            "Bring the items back to the shop. The money reaches your wallet once we have them.",
        ),
        "rejected": ("Return not possible", "We could not accept this return."),
        "received_credited": (
            "Return received",
            f"{rupees(refund_paise)} is in your wallet now.",
        ),
    }.get(status, ("Return updated", ""))
    title = f"{order_number}: {headline}"
    session.add(
        _add(
            session,
            profile_id=profile.id,
            kind=NotificationKind.system,
            title=title,
            body=note or detail,
            href=f"/orders/{order_number}",
        )
    )
    await _simple_email(
        session,
        profile=profile,
        subject=f"{order_number}: {headline}",
        lines=[note or detail, "", f"Order: {order_number}"],
        settings=settings,
        dedupe_key=f"return:{return_id}:{status}",
        anchor="You can follow this in Rewards and on the order page.",
    )


# --------------------------------------------------------------------------- #
# Reading the bell
# --------------------------------------------------------------------------- #
async def list_for_profile(
    session: AsyncSession, profile: Profile, *, page: int, page_size: int
) -> NotificationListOut:
    total = await repo.count_notifications(session, profile.id)
    rows = await repo.list_notifications(
        session, profile.id, limit=page_size, offset=(page - 1) * page_size
    )
    return NotificationListOut(
        items=[notification_out(row) for row in rows],
        unread_count=await repo.count_unread(session, profile.id),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


async def unread_count(session: AsyncSession, profile: Profile) -> int:
    return await repo.count_unread(session, profile.id)


async def mark_read(
    session: AsyncSession, profile: Profile, notification_id: uuid.UUID
) -> Notification:
    from app.core.errors import NotFoundError

    notification = await repo.get_notification(session, profile.id, notification_id)
    if notification is None:
        raise NotFoundError("No such notification.", code="notification_not_found")
    if notification.read_at is None:
        notification.read_at = datetime.now(tz=UTC)
        await session.commit()
        await session.refresh(notification)
    return notification


async def mark_all_read(session: AsyncSession, profile: Profile) -> int:
    marked = await repo.mark_all_read(session, profile.id, datetime.now(tz=UTC))
    await session.commit()
    return marked
