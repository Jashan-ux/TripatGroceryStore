"""Role isolation and the single-worker assigned delivery workflow."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import place, product_detail

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token('owner@example.com')}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin"
    return {"headers": headers, "profile": profile}


@pytest.fixture()
async def driver(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    email = f"driver-{uuid.uuid4().hex[:10]}@example.com"
    headers = {"Authorization": f"Bearer {make_token(email)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE profiles SET role = 'delivery' WHERE id = :id"),
            {"id": profile["id"]},
        )
        await session.commit()
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "delivery"
    return {"headers": headers, "profile": profile}


@pytest.fixture()
async def order(
    async_client: AsyncClient,
    customer: dict[str, Any],
    catalogue: dict[str, Any],
) -> dict[str, Any]:
    product = await product_detail(async_client, catalogue["ghee_slug"])
    placed = await place(
        async_client,
        customer,
        {"items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert placed.status_code == 201, placed.text
    return placed.json()


async def _set_admin_status(
    async_client: AsyncClient, admin: dict[str, Any], order_id: str, status: str
) -> Any:
    return await async_client.post(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": status},
        headers=admin["headers"],
    )


async def _ready_for_delivery(
    async_client: AsyncClient, admin: dict[str, Any], order_id: str
) -> None:
    for status in ("accepted", "packing", "shipped"):
        response = await _set_admin_status(async_client, admin, order_id, status)
        assert response.status_code == 200, response.text


async def test_role_gates_keep_driver_customer_and_admin_surfaces_separate(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    driver: dict[str, Any],
) -> None:
    driver_headers = driver["headers"]
    customer_headers = customer["headers"]

    response = await async_client.get("/api/v1/delivery/orders", headers=customer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "delivery_only"

    response = await async_client.get("/api/v1/admin/orders", headers=driver_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_only"

    response = await async_client.get("/api/v1/orders", headers=driver_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "customer_only"

    response = await async_client.get("/api/v1/delivery/orders", headers=admin["headers"])
    assert response.status_code == 403


async def test_default_driver_auto_assignment_and_assigned_order_isolation(
    async_client: AsyncClient,
    admin: dict[str, Any],
    driver: dict[str, Any],
    customer: dict[str, Any],
    order: dict[str, Any],
    make_token: Callable[..., str],
) -> None:
    headers = admin["headers"]
    profiles = await async_client.get("/api/v1/admin/delivery/profiles", headers=headers)
    assert profiles.status_code == 200, profiles.text
    assert driver["profile"]["id"] in {row["id"] for row in profiles.json()}
    assert customer["profile"]["id"] not in {row["id"] for row in profiles.json()}

    saved = await async_client.patch(
        "/api/v1/admin/settings",
        json={"default_delivery_profile_id": driver["profile"]["id"]},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["default_delivery_profile_id"] == driver["profile"]["id"]

    await _ready_for_delivery(async_client, admin, order["id"])
    assigned = await async_client.get("/api/v1/admin/orders", headers=headers)
    row = next(item for item in assigned.json()["items"] if item["id"] == order["id"])
    assert row["assigned_to"] == driver["profile"]["id"]
    assert row["assigned_driver_name"] == driver["profile"]["name"]

    visible = await async_client.get("/api/v1/delivery/orders", headers=driver["headers"])
    assert visible.status_code == 200, visible.text
    assert [item["id"] for item in visible.json()["items"]] == [order["id"]]
    delivery = visible.json()["items"][0]
    assert delivery["customer_phone"] == customer["phone"]
    assert delivery["address"]["pincode"] == "125104"
    assert delivery["items"][0]["quantity"] == 2
    assert delivery["total_paise"] == order["total_paise"]

    other_email = f"other-driver-{uuid.uuid4().hex[:10]}@example.com"
    other_headers = {"Authorization": f"Bearer {make_token(other_email)}"}
    other_profile = (await async_client.get("/api/v1/me", headers=other_headers)).json()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE profiles SET role = 'delivery' WHERE id = :id"),
            {"id": other_profile["id"]},
        )
        await session.commit()
    other_orders = await async_client.get("/api/v1/delivery/orders", headers=other_headers)
    assert other_orders.status_code == 200, other_orders.text
    assert other_orders.json()["items"] == []
    assert (
        await async_client.get("/api/v1/delivery/orders", headers=customer["headers"])
    ).status_code == 403


async def _event_count(order_id: str) -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM order_events WHERE order_id = :id"),
            {"id": order_id},
        )
    return int(count or 0)


async def test_driver_actions_are_forward_only_and_idempotent(
    async_client: AsyncClient,
    admin: dict[str, Any],
    driver: dict[str, Any],
    order: dict[str, Any],
) -> None:
    await _ready_for_delivery(async_client, admin, order["id"])
    headers = driver["headers"]
    order_url = f"/api/v1/admin/orders/{order['id']}/assignment"
    assigned = await async_client.patch(
        order_url,
        json={"profile_id": driver["profile"]["id"]},
        headers=admin["headers"],
    )
    assert assigned.status_code == 200, assigned.text

    base = f"/api/v1/delivery/orders/{order['id']}"
    too_early = await async_client.post(f"{base}/delivered", headers=headers)
    assert too_early.status_code == 409
    assert too_early.json()["error"]["code"] == "invalid_status_transition"

    dispatched = await async_client.post(f"{base}/out-for-delivery", headers=headers)
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == "out_for_delivery"
    assert dispatched.json()["out_for_delivery_at"] is not None

    event_count = await _event_count(order["id"])
    retry = await async_client.post(f"{base}/out-for-delivery", headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "out_for_delivery"
    assert await _event_count(order["id"]) == event_count

    delivered = await async_client.post(f"{base}/delivered", headers=headers)
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "delivered"
    assert delivered.json()["payment_status"] == "paid"
    assert delivered.json()["delivered_at"] is not None

    retry = await async_client.post(f"{base}/delivered", headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "delivered"
    assert retry.json()["delivered_at"] == delivered.json()["delivered_at"]
    assert await _event_count(order["id"]) == event_count + 1


async def test_admin_can_enable_a_customer_as_a_delivery_profile(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
) -> None:
    response = await async_client.post(
        "/api/v1/admin/delivery/profiles",
        json={"profile_id": customer["profile"]["id"]},
        headers=admin["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == customer["profile"]["id"]
    assert response.json()["phone"] == customer["phone"]

    updated = await async_client.get("/api/v1/me", headers=customer["headers"])
    assert updated.json()["role"] == "delivery"
    assert (
        await async_client.get("/api/v1/admin/delivery/profiles", headers=admin["headers"])
    ).json()[0]["id"] == customer["profile"]["id"]

    again = await async_client.post(
        "/api/v1/admin/delivery/profiles",
        json={"profile_id": customer["profile"]["id"]},
        headers=admin["headers"],
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "invalid_profile_role"


async def test_driver_cannot_read_or_mutate_unassigned_orders(
    async_client: AsyncClient,
    admin: dict[str, Any],
    driver: dict[str, Any],
    order: dict[str, Any],
) -> None:
    response = await async_client.post(
        f"/api/v1/delivery/orders/{order['id']}/out-for-delivery",
        headers=driver["headers"],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "delivery_order_not_found"

    invalid_driver = await async_client.patch(
        f"/api/v1/admin/orders/{order['id']}/assignment",
        json={"profile_id": admin["profile"]["id"]},
        headers=admin["headers"],
    )
    assert invalid_driver.status_code == 422
    assert invalid_driver.json()["error"]["code"] == "invalid_delivery_profile"
