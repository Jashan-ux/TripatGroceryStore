"""Shared setup helpers for the database-backed order tests.

These are *functions the tests call*, so they cannot be fixtures; they live here
rather than in a test module so the customer and admin suites share one
definition. Fixtures that use them (`customer`, `products`, `big_ticket`) are in
``tests/conftest.py``.

``pythonpath = ["."]`` in ``pyproject.toml`` keeps ``tests.support`` importable
however pytest is invoked (`pytest` alone does not add the working directory to
``sys.path`` the way `python -m pytest` does).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from httpx import AsyncClient

ADDRESS = {
    "label": "Home",
    "recipient_name": "Jashan Preet",
    "phone": "+91 98765-43210",
    "line1": "House 42, near Sabji Mandi",
    "line2": "Ward 7",
    "landmark": "Opposite Gyani Achhar Bhandaar",
    "pincode": "125104",
    "city": "Mandi Dabwali",
    "state": "Haryana",
}


async def product_detail(async_client: AsyncClient, slug: str) -> dict[str, Any]:
    response = await async_client.get(f"/api/v1/products/{slug}")
    assert response.status_code == 200, response.text
    return response.json()


async def new_customer(
    async_client: AsyncClient, make_token: Callable[..., str], *, prefix: str = "buyer"
) -> dict[str, Any]:
    """A signed-in customer with a phone number and one saved address."""
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    headers = {"Authorization": f"Bearer {make_token(email)}"}

    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    phone = "9" + str(uuid.uuid4().int)[:9]
    saved = await async_client.post("/api/v1/me/phone", json={"phone": phone}, headers=headers)
    assert saved.status_code == 200, saved.text
    address = await async_client.post("/api/v1/addresses", json=ADDRESS, headers=headers)
    assert address.status_code == 201, address.text
    return {
        "email": email,
        "headers": headers,
        "profile": profile,
        "address": address.json(),
        "phone": phone,
    }


def cart(*lines: tuple[dict[str, Any], int]) -> dict[str, Any]:
    return {
        "items": [
            {
                "product_id": product["id"],
                "variant_id": product.get("variant_id"),
                "quantity": quantity,
            }
            for product, quantity in lines
        ]
    }


async def stock_of(async_client: AsyncClient, slug: str) -> int:
    return int((await product_detail(async_client, slug))["stock"])


async def place(
    async_client: AsyncClient,
    customer: dict[str, Any],
    payload: dict[str, Any],
    *,
    key: str | None = None,
) -> Any:
    headers = dict(customer["headers"])
    if key is not None:
        headers["Idempotency-Key"] = key
    return await async_client.post(
        "/api/v1/orders",
        json={**payload, "address_id": customer["address"]["id"]},
        headers=headers,
    )
