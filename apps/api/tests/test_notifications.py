"""Database-backed tests for Phase 3: the bell, and the email outbox.

The invariants worth guarding, in the order they matter:

* a placed order notifies the **customer and every owner**, in the same
  transaction — and a rolled-back order notifies nobody;
* a notification is only ever readable by its own profile;
* the outbox is honest: with no provider it records ``skipped`` with a reason,
  with a provider it sends once, and flushing twice sends nothing twice.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from app.db.session import get_sessionmaker
from app.models.enums import EmailStatus
from app.services import email as email_service
from app.services import settings as settings_service
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import cart, new_customer, place, product_detail

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    return {"headers": headers, "profile": profile}


@pytest.fixture()
async def ghee(async_client: AsyncClient, catalogue: dict[str, Any]) -> dict[str, Any]:
    return await product_detail(async_client, catalogue["ghee_slug"])


async def _bell(async_client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await async_client.get("/api/v1/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _unread(async_client: AsyncClient, headers: dict[str, str]) -> int:
    response = await async_client.get("/api/v1/notifications/unread-count", headers=headers)
    assert response.status_code == 200, response.text
    return int(response.json()["unread_count"])


async def _place(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> dict[str, Any]:
    placed = await place(async_client, customer, cart((ghee, 2)))
    assert placed.status_code == 201, placed.text
    return placed.json()


def _fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured provider that never talks to Resend (the client is injected)."""

    class FakeSettings:
        RESEND_API_KEY = "re_test"
        SUPPORT_EMAIL_FROM = "Tripat Pansari <orders@example.invalid>"

    monkeypatch.setattr(email_service, "get_settings", FakeSettings)


async def _emails() -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT to_email, subject, status, dedupe_key, attempts, last_error "
                    "FROM email_messages ORDER BY created_at"
                )
            )
        ).mappings()
        return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# Writing the bell
# --------------------------------------------------------------------------- #
async def test_placing_an_order_rings_the_customer_and_the_owner(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _place(async_client, customer, ghee)

    bell = await _bell(async_client, customer["headers"])
    assert bell["unread_count"] == 1
    entry = bell["items"][0]
    assert entry["kind"] == "order_placed"
    assert order["order_number"] in entry["title"]
    assert entry["href"] == f"/orders/{order['id']}"
    assert entry["read"] is False
    assert "cash on delivery" in entry["body"]

    owner_bell = await _bell(async_client, admin["headers"])
    assert owner_bell["unread_count"] == 1
    owner_entry = owner_bell["items"][0]
    assert owner_entry["kind"] == "new_order"
    assert owner_entry["href"] == "/admin/orders"
    assert order["order_number"] in owner_entry["title"]


async def test_a_failed_checkout_notifies_nobody(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    """The notification is written inside the order transaction, so it is atomic."""
    refused = await place(async_client, customer, cart((ghee, ghee["stock"] + 5)))
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "insufficient_stock"
    assert (await _bell(async_client, customer["headers"]))["items"] == []


async def test_the_bell_is_private(
    async_client: AsyncClient,
    customer: dict[str, Any],
    ghee: dict[str, Any],
    make_token: Callable[..., str],
) -> None:
    for _ in range(2):
        await _place(async_client, customer, ghee)

    other = await new_customer(async_client, make_token, prefix="nosy")
    assert (await _bell(async_client, other["headers"]))["items"] == []

    mine = (await _bell(async_client, customer["headers"]))["items"]
    stolen = await async_client.post(
        f"/api/v1/notifications/{mine[0]['id']}/ack", headers=other["headers"]
    )
    assert stolen.status_code == 404
    assert stolen.json()["error"]["code"] == "notification_not_found"

    anonymous = await async_client.get("/api/v1/notifications")
    assert anonymous.status_code == 401


async def test_ack_and_read_all_move_the_red_dot(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    for _ in range(3):
        await _place(async_client, customer, ghee)
    assert await _unread(async_client, customer["headers"]) == 3

    first = (await _bell(async_client, customer["headers"]))["items"][0]
    ack = await async_client.post(
        f"/api/v1/notifications/{first['id']}/ack", headers=customer["headers"]
    )
    assert ack.status_code == 200
    assert ack.json()["read"] is True
    assert await _unread(async_client, customer["headers"]) == 2

    # Acknowledging again is harmless, not an error.
    again = await async_client.post(
        f"/api/v1/notifications/{first['id']}/ack", headers=customer["headers"]
    )
    assert again.status_code == 200
    assert await _unread(async_client, customer["headers"]) == 2

    cleared = await async_client.post("/api/v1/notifications/read-all", headers=customer["headers"])
    assert cleared.status_code == 200
    assert cleared.json()["marked"] == 2
    assert await _unread(async_client, customer["headers"]) == 0
    # Nothing left to clear, and the bell still lists what happened.
    assert (
        await async_client.post("/api/v1/notifications/read-all", headers=customer["headers"])
    ).json()["marked"] == 0
    assert (await _bell(async_client, customer["headers"]))["total"] == 3


async def test_the_bell_pages(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    for _ in range(3):
        await _place(async_client, customer, ghee)
    page = await async_client.get(
        "/api/v1/notifications", params={"page": 1, "page_size": 2}, headers=customer["headers"]
    )
    body = page.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert body["unread_count"] == 3
    # Newest first.
    assert body["items"][0]["created_at"] >= body["items"][1]["created_at"]


# --------------------------------------------------------------------------- #
# Status changes
# --------------------------------------------------------------------------- #
async def test_shop_transitions_ring_the_customer(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _place(async_client, customer, ghee)
    await async_client.post("/api/v1/notifications/read-all", headers=customer["headers"])

    shipped = await async_client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "shipped"},
        headers=admin["headers"],
    )
    assert shipped.status_code == 200, shipped.text

    bell = await _bell(async_client, customer["headers"])
    entry = bell["items"][0]
    assert entry["kind"] == "order_status"
    assert entry["title"] == f"{order['order_number']}: Packed and shipped"
    assert entry["href"] == f"/orders/{order['id']}"
    assert bell["unread_count"] == 1

    # Delivered says so, and settles the payment in the order itself.
    await async_client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "out_for_delivery"},
        headers=admin["headers"],
    )
    await async_client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "delivered"},
        headers=admin["headers"],
    )
    titles = [item["title"] for item in (await _bell(async_client, customer["headers"]))["items"]]
    assert f"{order['order_number']}: Delivered" in titles


async def test_cancellation_and_its_reason_reach_the_customer(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _place(async_client, customer, ghee)
    await async_client.post("/api/v1/notifications/read-all", headers=customer["headers"])

    cancelled = await async_client.post(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "Sorry, the ghee ran out"},
        headers=admin["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text

    entry = (await _bell(async_client, customer["headers"]))["items"][0]
    assert entry["kind"] == "order_cancelled"
    assert entry["body"] == "Sorry, the ghee ran out"

    # And the customer's own cancellation tells them too.
    second = await _place(async_client, customer, ghee)
    mine = await async_client.post(
        f"/api/v1/orders/{second['id']}/cancel",
        json={"reason": "changed my mind"},
        headers=customer["headers"],
    )
    assert mine.status_code == 200, mine.text
    latest = (await _bell(async_client, customer["headers"]))["items"][0]
    assert latest["kind"] == "order_cancelled"
    assert latest["body"] == "changed my mind"


async def test_a_customer_cancellation_rings_the_shop(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _place(async_client, customer, ghee)
    await async_client.post("/api/v1/notifications/read-all", headers=admin["headers"])

    cancelled = await async_client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "ordered by mistake"},
        headers=customer["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text

    bell = await _bell(async_client, admin["headers"])
    assert bell["unread_count"] == 1
    entry = bell["items"][0]
    assert entry["kind"] == "order_cancelled"
    assert entry["title"] == f"{order['order_number']} cancelled by the customer"
    assert entry["href"] == "/admin/orders"
    # The customer still sees their own side of it.
    mine = (await _bell(async_client, customer["headers"]))["items"][0]
    assert mine["title"] == f"{order['order_number']}: Order cancelled"


# --------------------------------------------------------------------------- #
# The outbox
# --------------------------------------------------------------------------- #
async def test_the_confirmation_and_the_shop_alert_are_queued(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _place(async_client, customer, ghee)

    rows = await _emails()
    to_addresses = {row["to_email"] for row in rows}
    assert customer["email"].lower() in to_addresses
    assert ADMIN_EMAIL in to_addresses
    assert all(row["status"] == "queued" for row in rows)

    customer_mail = next(row for row in rows if row["to_email"] == customer["email"].lower())
    assert order["order_number"] in customer_mail["subject"]
    # Dedupe keys are per order + purpose, so a replay can never double-mail.
    assert customer_mail["dedupe_key"].startswith(f"order:{order['id']}:")


async def test_without_a_provider_the_outbox_says_so_and_sends_nothing(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    await _place(async_client, customer, ghee)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        counts = await email_service.flush(session)
    assert counts == {"sent": 0, "skipped": 2, "failed": 0}

    rows = await _emails()
    assert {row["status"] for row in rows} == {"skipped"}
    assert all("RESEND_API_KEY" in row["last_error"] for row in rows)

    # Nothing is retried forever: a second flush finds nothing queued.
    async with sessionmaker() as session:
        assert await email_service.flush(session) == {"sent": 0, "skipped": 0, "failed": 0}


async def test_with_a_provider_each_email_is_sent_once(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_provider(monkeypatch)
    await _place(async_client, customer, ghee)

    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"id": "email_1"})

    sessionmaker = get_sessionmaker()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        async with sessionmaker() as session:
            counts = await email_service.flush(session, client=client)
        assert counts == {"sent": 2, "skipped": 0, "failed": 0}
        # Draining again sends nothing: the rows are no longer `queued`.
        async with sessionmaker() as session:
            drained = await email_service.flush(session, client=client)
            assert drained["sent"] == 0

    assert len(sent) == 2
    assert sent[0].headers["authorization"] == "Bearer re_test"
    assert {str(request.headers.get("authorization")) for request in sent} == {"Bearer re_test"}

    rows = await _emails()
    assert {row["status"] for row in rows} == {"sent"}
    assert all(row["attempts"] == 1 and row["last_error"] == "" for row in rows)


async def test_a_provider_error_is_recorded_not_swallowed(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_provider(monkeypatch)
    await _place(async_client, customer, ghee)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="resend is having a day")

    sessionmaker = get_sessionmaker()
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
        sessionmaker() as session,
    ):
        counts = await email_service.flush(session, client=client)
    assert counts["failed"] == 2

    rows = await _emails()
    assert {row["status"] for row in rows} == {"failed"}
    assert all("HTTP 500" in row["last_error"] for row in rows)


# --------------------------------------------------------------------------- #
# The settings cache (regression guard for a bug CI caught in Phase 2)
# --------------------------------------------------------------------------- #
async def test_notification_copy_uses_the_live_settings_row(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    settings_service.invalidate_cache()
    order = await _place(async_client, customer, ghee)
    entry = (await _bell(async_client, customer["headers"]))["items"][0]
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        store_name = await session.scalar(text("SELECT store_name FROM store_settings WHERE id=1"))
    assert store_name
    assert order["order_number"] in entry["title"]
    assert uuid.UUID(entry["order_id"]) == uuid.UUID(order["id"])
    settings_service.invalidate_cache()


async def test_email_status_values_are_the_ones_the_database_has() -> None:
    """The enum is native in Postgres; a typo in Python would only show up in prod."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        labels = set(
            (
                await session.execute(
                    text("SELECT unnest(enum_range(NULL::email_status))::text AS label")
                )
            ).scalars()
        )
    assert labels == {status.value for status in EmailStatus}
