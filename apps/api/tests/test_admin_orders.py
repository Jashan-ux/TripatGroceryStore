"""Database-backed tests for the owner's order queue.

Covers the gate (customers cannot see the queue), the listing filters the shop
actually uses on a phone, and every status transition including the two with side
effects: a cancel puts stock back, a delivery settles the COD payment.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import ADDRESS, cart, place, stock_of

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    """The store owner: a signed-in profile whose email is in ADMIN_EMAILS."""
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers, "profile": profile}


@pytest.fixture()
async def order(
    async_client: AsyncClient,
    customer: dict[str, Any],
    catalogue: dict[str, Any],
) -> dict[str, Any]:
    """One real order with two lines, placed through the customer API."""
    ghee = (await async_client.get(f"/api/v1/products/{catalogue['ghee_slug']}")).json()
    loose = (await async_client.get(f"/api/v1/products/{catalogue['loose_slug']}")).json()
    placed = await place(async_client, customer, cart((ghee, 2), (loose, 3)))
    assert placed.status_code == 201, placed.text
    return placed.json()


def _set_status(
    async_client: AsyncClient, admin: dict[str, Any], order_id: str, status: str, note: str = ""
) -> Any:
    return async_client.post(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": status, "note": note},
        headers=admin["headers"],
    )


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #
async def test_customers_cannot_reach_the_queue(
    async_client: AsyncClient, customer: dict[str, Any], order: dict[str, Any]
) -> None:
    queue = await async_client.get("/api/v1/admin/orders", headers=customer["headers"])
    assert queue.status_code == 403
    assert queue.json()["error"]["code"] == "admin_only"

    detail = await async_client.get(
        f"/api/v1/admin/orders/{order['id']}", headers=customer["headers"]
    )
    assert detail.status_code == 403

    move = await _set_status(async_client, customer, order["id"], "shipped")
    assert move.status_code == 403

    anonymous = await async_client.get("/api/v1/admin/orders")
    assert anonymous.status_code == 401


# --------------------------------------------------------------------------- #
# The queue
# --------------------------------------------------------------------------- #
async def test_the_queue_shows_who_ordered_what(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    order: dict[str, Any],
) -> None:
    response = await async_client.get("/api/v1/admin/orders", headers=admin["headers"])
    assert response.status_code == 200, response.text
    body = response.json()

    row = next(item for item in body["items"] if item["id"] == order["id"])
    assert row["order_number"] == order["order_number"]
    assert row["status"] == "processing"
    assert row["payment_status"] == "pending"
    assert row["customer_phone"] == customer["phone"]
    assert row["total_paise"] == order["total_paise"]
    assert row["first_item_name"]
    assert row["is_new"] is True

    # Counts cover the whole shop, not just this page.
    assert body["counts"]["processing"] >= 1
    assert set(body["counts"]) == {
        "processing",
        "shipped",
        "out_for_delivery",
        "delivered",
        "cancelled",
        "returned",
    }


async def test_filters_by_status_and_searches_by_number_or_phone(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    order: dict[str, Any],
) -> None:
    headers = admin["headers"]

    processing = await async_client.get(
        "/api/v1/admin/orders", params={"status": "processing"}, headers=headers
    )
    assert order["id"] in {row["id"] for row in processing.json()["items"]}
    assert all(row["status"] == "processing" for row in processing.json()["items"])

    delivered = await async_client.get(
        "/api/v1/admin/orders", params={"status": "delivered"}, headers=headers
    )
    assert order["id"] not in {row["id"] for row in delivered.json()["items"]}

    by_number = await async_client.get(
        "/api/v1/admin/orders", params={"q": order["order_number"]}, headers=headers
    )
    assert [row["id"] for row in by_number.json()["items"]] == [order["id"]]

    by_phone = await async_client.get(
        "/api/v1/admin/orders", params={"q": customer["phone"]}, headers=headers
    )
    assert order["id"] in {row["id"] for row in by_phone.json()["items"]}

    nothing = await async_client.get(
        "/api/v1/admin/orders", params={"q": "zzz-no-such-order"}, headers=headers
    )
    assert nothing.json()["items"] == []
    assert nothing.json()["total"] == 0


async def test_the_queue_pages(
    async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]
) -> None:
    first = await async_client.get(
        "/api/v1/admin/orders", params={"page_size": 1}, headers=admin["headers"]
    )
    body = first.json()
    assert len(body["items"]) == 1
    assert body["page_size"] == 1
    assert body["total_pages"] >= 1
    assert body["total"] >= 1


async def test_an_unknown_order_is_a_404(async_client: AsyncClient, admin: dict[str, Any]) -> None:
    response = await async_client.get(
        f"/api/v1/admin/orders/{uuid.uuid4()}", headers=admin["headers"]
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "order_not_found"


async def test_detail_carries_the_timeline(
    async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]
) -> None:
    response = await async_client.get(
        f"/api/v1/admin/orders/{order['id']}", headers=admin["headers"]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["order_number"] == order["order_number"]
    assert [event["status"] for event in body["events"]] == ["processing"]
    assert body["address"]["pincode"] == ADDRESS["pincode"]


# --------------------------------------------------------------------------- #
# Transitions
# --------------------------------------------------------------------------- #
async def test_the_happy_path_settles_the_cash_on_delivery(
    async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]
) -> None:
    for status in ("shipped", "out_for_delivery", "delivered"):
        response = await _set_status(async_client, admin, order["id"], status)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status
        if status != "delivered":
            assert response.json()["payment_status"] == "pending"

    settled = await async_client.get(
        f"/api/v1/admin/orders/{order['id']}", headers=admin["headers"]
    )
    body = settled.json()
    assert body["status"] == "delivered"
    assert body["payment_status"] == "paid"
    assert [event["status"] for event in body["events"]] == [
        "processing",
        "shipped",
        "out_for_delivery",
        "delivered",
    ]
    assert {event["actor"] for event in body["events"][1:]} == {"admin"}


async def test_a_skipped_step_is_refused_with_the_allowed_moves(
    async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]
) -> None:
    response = await _set_status(async_client, admin, order["id"], "delivered")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "invalid_status_transition"
    assert error["details"]["status"] == "processing"
    assert sorted(error["details"]["allowed"]) == ["cancelled", "shipped"]


async def test_cancelling_from_the_queue_puts_the_stock_back(
    async_client: AsyncClient,
    admin: dict[str, Any],
    order: dict[str, Any],
    catalogue: dict[str, Any],
) -> None:
    before = await stock_of(async_client, catalogue["ghee_slug"])

    response = await _set_status(
        async_client, admin, order["id"], "cancelled", note="Customer called the shop"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert await stock_of(async_client, catalogue["ghee_slug"]) == before + 2

    detail = (
        await async_client.get(f"/api/v1/admin/orders/{order['id']}", headers=admin["headers"])
    ).json()
    assert detail["cancelled_reason"] == "Customer called the shop"
    assert detail["cancelled_at"] is not None
    assert detail["events"][-1]["actor"] == "admin"
    assert detail["events"][-1]["note"] == "Customer called the shop"

    # A cancelled order is final.
    again = await _set_status(async_client, admin, order["id"], "shipped")
    assert again.status_code == 409


async def test_a_dispatched_order_can_no_longer_be_cancelled(
    async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]
) -> None:
    assert (await _set_status(async_client, admin, order["id"], "shipped")).status_code == 200
    refused = await _set_status(async_client, admin, order["id"], "cancelled")
    assert refused.status_code == 409
    assert refused.json()["error"]["details"]["allowed"] == ["out_for_delivery"]


async def test_an_unknown_status_is_rejected_by_validation(
    async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]
) -> None:
    response = await async_client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "teleported"},
        headers=admin["headers"],
    )
    assert response.status_code == 422


async def test_a_customer_cancellation_and_a_shop_cancellation_agree(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    order: dict[str, Any],
    catalogue: dict[str, Any],
) -> None:
    """The queue must reflect a cancellation the customer made in the app."""
    cancelled = await async_client.post(
        f"/api/v1/orders/{order['id']}/cancel", json={"reason": ""}, headers=customer["headers"]
    )
    assert cancelled.status_code == 200

    queue = (
        await async_client.get(
            "/api/v1/admin/orders", params={"status": "cancelled"}, headers=admin["headers"]
        )
    ).json()
    assert order["id"] in {row["id"] for row in queue["items"]}

    # And the shop cannot resurrect it.
    assert (await _set_status(async_client, admin, order["id"], "shipped")).status_code == 409


async def test_stock_is_restored_exactly_once_even_for_two_lines(
    async_client: AsyncClient,
    admin: dict[str, Any],
    order: dict[str, Any],
    catalogue: dict[str, Any],
) -> None:
    ghee_before = await stock_of(async_client, catalogue["ghee_slug"])
    loose_before = await stock_of(async_client, catalogue["loose_slug"])

    assert (await _set_status(async_client, admin, order["id"], "cancelled")).status_code == 200

    assert await stock_of(async_client, catalogue["ghee_slug"]) == ghee_before + 2
    assert await stock_of(async_client, catalogue["loose_slug"]) == loose_before + 3

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        events = await session.scalar(
            text("SELECT count(*) FROM order_events WHERE order_id = :id AND status = 'cancelled'"),
            {"id": order["id"]},
        )
    assert events == 1
