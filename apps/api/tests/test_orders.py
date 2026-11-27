"""Database-backed tests for Phase 2: addresses, quotes, orders, stock, cancel.

Marked ``db``: they skip locally unless ``TEST_DATABASE_URL`` is set and run in CI
against the Postgres service container after `alembic upgrade head`.

Every payload below sends ids and quantities only — never money — and asserts on
what the server computed from the catalogue.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import ADDRESS, cart, new_customer, place, product_detail, stock_of

# Orders need a signed-in customer, so every test verifies tokens against the
# local key set instead of the project's JWKS.
pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]


async def test_the_cached_settings_row_never_needs_its_session() -> None:
    """A rollback elsewhere must not expire the cached store settings.

    The cache used to hold the live ORM row, so any request that rolled back
    after loading it left an expired, detached object behind and every checkout
    inside the 30-second window then raised ``DetachedInstanceError``.
    """
    from app.db.session import get_sessionmaker
    from app.services import settings as settings_service

    settings_service.invalidate_cache()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        loaded = await settings_service.get_store_settings(session)
        await session.rollback()

    assert loaded.minimum_order_paise > 0
    assert loaded.serviceable_pincodes
    assert loaded.default_delivery_days >= 1
    settings_service.invalidate_cache()


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
async def test_address_crud_and_default_handling(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    headers = customer["headers"]
    listed = await async_client.get("/api/v1/addresses", headers=headers)
    assert listed.status_code == 200
    assert [row["is_default"] for row in listed.json()] == [True]  # first one is default

    second = await async_client.post(
        "/api/v1/addresses",
        json={**ADDRESS, "label": "Shop", "line1": "Shop 3, Grain Market", "is_default": True},
        headers=headers,
    )
    assert second.status_code == 201

    edited = await async_client.put(
        f"/api/v1/addresses/{second.json()['id']}",
        json={
            **ADDRESS,
            "label": "Shop",
            "line1": "Shop 4, Grain Market",
            "phone": "+91 98765-43210",
            "is_default": True,
        },
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["line1"] == "Shop 4, Grain Market"
    assert edited.json()["phone"] == "9876543210"

    rows = (await async_client.get("/api/v1/addresses", headers=headers)).json()
    assert len(rows) == 2
    assert sum(1 for row in rows if row["is_default"]) == 1
    assert next(row for row in rows if row["is_default"])["label"] == "Shop"

    # Deleting the default promotes the survivor, so an order can always be placed.
    deleted = await async_client.delete(f"/api/v1/addresses/{second.json()['id']}", headers=headers)
    assert deleted.status_code == 204
    remaining = (await async_client.get("/api/v1/addresses", headers=headers)).json()
    assert [row["is_default"] for row in remaining] == [True]


async def test_addresses_are_invisible_to_other_customers(
    async_client: AsyncClient, customer: dict[str, Any], make_token: Callable[..., str]
) -> None:
    other = await new_customer(async_client, make_token, prefix="other")
    listed = (await async_client.get("/api/v1/addresses", headers=other["headers"])).json()
    # The other customer has an address of their own — and only that one.
    assert [row["id"] for row in listed] == [other["address"]["id"]]
    assert customer["address"]["id"] not in {row["id"] for row in listed}
    stolen = await async_client.delete(
        f"/api/v1/addresses/{customer['address']['id']}", headers=other["headers"]
    )
    assert stolen.status_code == 404


async def test_a_malformed_pincode_is_rejected(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    response = await async_client.post(
        "/api/v1/addresses", json={**ADDRESS, "pincode": "12"}, headers=customer["headers"]
    )
    assert response.status_code == 422


async def test_the_address_phone_is_normalised(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    assert customer["address"]["phone"] == "9876543210"


# --------------------------------------------------------------------------- #
# Quotes — pricing is computed, never accepted
# --------------------------------------------------------------------------- #
async def test_quote_prices_the_cart_from_the_database(
    async_client: AsyncClient, products: dict[str, Any]
) -> None:
    ghee = products["ghee"]
    response = await async_client.post("/api/v1/checkout/quote", json=cart((ghee, 2)))
    assert response.status_code == 200
    body = response.json()
    line = body["lines"][0]
    assert line["unit_price_paise"] == ghee["price_paise"]
    assert line["line_total_paise"] == ghee["price_paise"] * 2
    assert body["subtotal_paise"] == body["total_paise"] == line["line_total_paise"]
    assert body["item_count"] == 2
    assert body["delivery_fee_paise"] == 0
    assert body["minimum_order_paise"] == 50_000
    assert body["can_checkout"] is True


async def test_quote_reports_the_exact_shortfall_under_the_minimum(
    async_client: AsyncClient, products: dict[str, Any]
) -> None:
    ghee = products["ghee"]
    assert ghee["price_paise"] < 50_000  # one pack is under the ₹500 minimum
    body = (await async_client.post("/api/v1/checkout/quote", json=cart((ghee, 1)))).json()

    shortfall = 50_000 - ghee["price_paise"]
    assert body["subtotal_paise"] == ghee["price_paise"]
    assert body["shortfall_paise"] == shortfall
    assert body["can_checkout"] is False
    assert [issue["code"] for issue in body["blocking_issues"]] == ["minimum_order"]
    assert f"₹{shortfall // 100}" in body["blocking_issues"][0]["message"]


async def test_quote_flags_an_unserviceable_pincode(
    async_client: AsyncClient, products: dict[str, Any]
) -> None:
    payload = {**cart((products["ghee"], 2)), "pincode": "110001"}
    body = (await async_client.post("/api/v1/checkout/quote", json=payload)).json()
    codes = [issue["code"] for issue in body["blocking_issues"]]
    assert "pincode" in codes
    assert body["pincode_serviceable"] is False
    assert body["can_checkout"] is False


async def test_quote_accepts_a_serviceable_pincode(
    async_client: AsyncClient, products: dict[str, Any]
) -> None:
    payload = {**cart((products["ghee"], 2)), "pincode": "125104"}
    body = (await async_client.post("/api/v1/checkout/quote", json=payload)).json()
    assert body["pincode_serviceable"] is True
    assert body["blocking_issues"] == []
    assert body["can_checkout"] is True


async def test_quote_flags_an_unknown_product_without_crashing(
    async_client: AsyncClient,
) -> None:
    body = (
        await async_client.post(
            "/api/v1/checkout/quote",
            json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
        )
    ).json()
    assert body["lines"][0]["issue"] == "unavailable"
    assert body["lines"][0]["line_total_paise"] == 0
    assert body["subtotal_paise"] == 0
    assert body["can_checkout"] is False


async def test_quote_reports_stock_shortfall_for_the_requested_quantity(
    async_client: AsyncClient, products: dict[str, Any]
) -> None:
    loose = products["loose"]
    variant = next(entry for entry in loose["variants"] if entry["stock"] > 0)
    body = (
        await async_client.post(
            "/api/v1/checkout/quote",
            json={
                "items": [
                    {
                        "product_id": loose["id"],
                        "variant_id": variant["id"],
                        "quantity": variant["stock"] + 1,
                    }
                ]
            },
        )
    ).json()
    line = body["lines"][0]
    assert line["issue"] == "partially_available"
    assert line["available_stock"] == variant["stock"]
    assert line["line_total_paise"] == 0
    # Nothing is billable, so the minimum-order rule is honestly reported too.
    codes = [issue["code"] for issue in body["blocking_issues"]]
    assert codes[0] == "stock"
    assert body["subtotal_paise"] == 0
    assert body["can_checkout"] is False


# --------------------------------------------------------------------------- #
# Placing an order
# --------------------------------------------------------------------------- #
async def test_placing_an_order_snapshots_prices_and_decrements_stock(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    ghee = products["ghee"]
    before = await stock_of(async_client, ghee["slug"])

    response = await place(async_client, customer, cart((ghee, 2)))
    assert response.status_code == 201, response.text

    order = response.json()
    assert order["status"] == "processing"
    assert order["payment_method"] == "cod"
    assert order["payment_status"] == "pending"
    assert order["order_number"].startswith("MSG-")
    assert order["subtotal_paise"] == ghee["price_paise"] * 2
    assert order["total_paise"] == order["subtotal_paise"]
    assert order["item_count"] == 2
    assert order["customer_phone"] == customer["phone"]
    assert order["address"]["pincode"] == "125104"
    assert order["deliver_by"] is not None
    assert [event["status"] for event in order["events"]] == ["processing"]
    assert order["events"][0]["actor"] == "customer"
    assert order["items"][0]["unit_price_paise"] == ghee["price_paise"]
    assert await stock_of(async_client, ghee["slug"]) == before - 2


async def test_variant_stock_is_decremented_on_the_variant(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    loose = products["loose"]
    variant = next(entry for entry in loose["variants"] if entry["stock"] >= 5)
    quantity = 5  # 5 × ₹115 = ₹575, above the ₹500 minimum

    response = await place(
        async_client,
        customer,
        {"items": [{"product_id": loose["id"], "variant_id": variant["id"], "quantity": quantity}]},
    )
    assert response.status_code == 201, response.text

    detail = await product_detail(async_client, loose["slug"])
    after = next(entry for entry in detail["variants"] if entry["id"] == variant["id"])
    assert after["stock"] == variant["stock"] - quantity
    assert response.json()["items"][0]["variant_label"] == variant["label"]


async def test_money_in_the_payload_is_refused(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    """S-03: the schema forbids money keys outright rather than ignoring them."""
    ghee = products["ghee"]
    response = await async_client.post(
        "/api/v1/orders",
        json={
            "items": [
                {
                    "product_id": ghee["id"],
                    "quantity": 2,
                    "unit_price_paise": 1,
                    "line_total_paise": 1,
                }
            ],
            "address_id": customer["address"]["id"],
            "total_paise": 1,
        },
        headers=customer["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_order_below_the_minimum_is_refused_with_the_shortfall(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    response = await place(async_client, customer, cart((products["ghee"], 1)))
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "minimum_order_not_met"
    assert body["details"]["shortfall_paise"] == 50_000 - products["ghee"]["price_paise"]


async def test_order_requires_a_phone_number(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    products: dict[str, Any],
) -> None:
    email = f"nophone-{uuid.uuid4().hex[:8]}@example.com"
    headers = {"Authorization": f"Bearer {make_token(email)}"}
    await async_client.get("/api/v1/me", headers=headers)
    address = await async_client.post("/api/v1/addresses", json=ADDRESS, headers=headers)
    assert address.status_code == 201

    response = await async_client.post(
        "/api/v1/orders",
        json={**cart((products["ghee"], 2)), "address_id": address.json()["id"]},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "phone_required"


async def test_order_in_an_unserviceable_pincode_is_refused(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    far = await async_client.post(
        "/api/v1/addresses",
        json={**ADDRESS, "label": "Far", "pincode": "110001"},
        headers=customer["headers"],
    )
    assert far.status_code == 201

    response = await async_client.post(
        "/api/v1/orders",
        json={**cart((products["ghee"], 2)), "address_id": far.json()["id"]},
        headers=customer["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pincode_not_serviceable"


async def test_more_than_available_stock_is_refused(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    ghee = products["ghee"]
    available = await stock_of(async_client, ghee["slug"])
    response = await place(async_client, customer, cart((ghee, available + 1)))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    assert await stock_of(async_client, ghee["slug"]) == available  # nothing moved


async def test_a_replayed_checkout_returns_the_original_order(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    key = f"test-{uuid.uuid4()}"
    ghee = products["ghee"]
    before = await stock_of(async_client, ghee["slug"])

    first = await place(async_client, customer, cart((ghee, 2)), key=key)
    second = await place(async_client, customer, cart((ghee, 2)), key=key)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["order_number"] == second.json()["order_number"]
    assert await stock_of(async_client, ghee["slug"]) == before - 2


async def test_the_last_units_have_exactly_one_winner_each(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    big_ticket: dict[str, Any],
) -> None:
    """S-04: seven different customers race for a product with three units."""
    customers = [await new_customer(async_client, make_token, prefix="race") for _ in range(7)]

    responses = await asyncio.gather(
        *[
            place(async_client, buyer, cart((big_ticket, 1)), key=f"race-{uuid.uuid4()}")
            for buyer in customers
        ]
    )
    created = [response for response in responses if response.status_code == 201]
    refused = [response for response in responses if response.status_code == 409]

    assert len(created) == 3
    assert len(created) + len(refused) == len(customers)
    assert all(response.json()["error"]["code"] == "insufficient_stock" for response in refused)
    assert await stock_of(async_client, big_ticket["slug"]) == 0


# --------------------------------------------------------------------------- #
# Reading and cancelling
# --------------------------------------------------------------------------- #
async def test_orders_are_listed_and_scoped_to_the_owner(
    async_client: AsyncClient,
    customer: dict[str, Any],
    products: dict[str, Any],
    make_token: Callable[..., str],
) -> None:
    placed = await place(async_client, customer, cart((products["ghee"], 2)))
    assert placed.status_code == 201, placed.text
    order_id = placed.json()["id"]

    listed = await async_client.get("/api/v1/orders", headers=customer["headers"])
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == order_id
    assert body["items"][0]["first_item_name"] == products["ghee"]["name"]

    detail = await async_client.get(f"/api/v1/orders/{order_id}", headers=customer["headers"])
    assert detail.status_code == 200
    assert detail.json()["items"][0]["quantity"] == 2

    other = await new_customer(async_client, make_token, prefix="other")
    assert (await async_client.get("/api/v1/orders", headers=other["headers"])).json()["total"] == 0
    assert (
        await async_client.get(f"/api/v1/orders/{order_id}", headers=other["headers"])
    ).status_code == 404
    assert (
        await async_client.post(
            f"/api/v1/orders/{order_id}/cancel", json={}, headers=other["headers"]
        )
    ).status_code == 404


async def test_cancelling_restores_stock_and_cannot_be_repeated(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    ghee = products["ghee"]
    before = await stock_of(async_client, ghee["slug"])
    placed = await place(async_client, customer, cart((ghee, 2)))
    assert placed.status_code == 201
    order_id = placed.json()["id"]
    assert await stock_of(async_client, ghee["slug"]) == before - 2

    cancelled = await async_client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": "Ordered by mistake"},
        headers=customer["headers"],
    )
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["cancelled_reason"] == "Ordered by mistake"
    assert [event["status"] for event in body["events"]] == ["processing", "cancelled"]
    assert await stock_of(async_client, ghee["slug"]) == before

    again = await async_client.post(
        f"/api/v1/orders/{order_id}/cancel", json={}, headers=customer["headers"]
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "order_not_cancellable"
    # A second cancel must not restore stock twice.
    assert await stock_of(async_client, ghee["slug"]) == before


async def test_an_order_cannot_be_cancelled_once_it_has_shipped(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    placed = await place(async_client, customer, cart((products["ghee"], 2)))
    order_id = placed.json()["id"]

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE orders SET status = :status WHERE id = :id"),
            {"status": "shipped", "id": order_id},
        )
        await session.commit()

    response = await async_client.post(
        f"/api/v1/orders/{order_id}/cancel", json={}, headers=customer["headers"]
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "order_not_cancellable"


async def test_the_timeline_records_events_not_the_current_status(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    placed = await place(async_client, customer, cart((products["ghee"], 2)))
    order_id = placed.json()["id"]

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE orders SET status = 'delivered' WHERE id = :id"), {"id": order_id}
        )
        await session.commit()

    detail = (
        await async_client.get(f"/api/v1/orders/{order_id}", headers=customer["headers"])
    ).json()
    assert [event["status"] for event in detail["events"]] == ["processing"]
    assert detail["status"] == "delivered"


async def test_the_price_snapshot_survives_a_catalogue_edit(
    async_client: AsyncClient, customer: dict[str, Any], products: dict[str, Any]
) -> None:
    ghee = products["ghee"]
    placed = await place(async_client, customer, cart((ghee, 2)))
    assert placed.status_code == 201

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE products SET price_paise = :price WHERE id = :id"),
            {"price": ghee["price_paise"] + 10_000, "id": ghee["id"]},
        )
        await session.commit()

    detail = (
        await async_client.get(f"/api/v1/orders/{placed.json()['id']}", headers=customer["headers"])
    ).json()
    assert detail["items"][0]["unit_price_paise"] == ghee["price_paise"]
    assert detail["total_paise"] == ghee["price_paise"] * 2
