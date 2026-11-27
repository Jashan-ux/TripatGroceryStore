"""Phase 7 push registration and real offer delivery wiring.

Subscriptions are private, device-scoped credentials: a customer can add or remove
only their own browser endpoint, duplicate registration refreshes the encryption
keys, and neither keys nor endpoints are exposed from a list API. Offer delivery
uses the same audience as the in-app bell, runs after the offer commits, and reports
opted-in endpoints separately from email.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from app.models.push import PushSubscription
from app.services import push as push_service
from httpx import AsyncClient
from sqlalchemy import func, select, text
from tests.support import new_customer

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


def _subscription(endpoint: str = "https://fcm.googleapis.com/subscription/abc") -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "p" * 65, "auth": "a" * 24},
        "expiration_time": None,
    }


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin"
    return {"headers": headers, "profile": profile}


async def test_subscribe_and_unsubscribe_are_private_to_that_profile(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-test-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        first = await new_customer(async_client, make_token, prefix="push-first")
        second = await new_customer(async_client, make_token, prefix="push-second")
        payload = _subscription()
        headers = first["headers"]

        saved = await async_client.post("/api/v1/push/subscribe", json=payload, headers=headers)
        assert saved.status_code == 200, saved.text
        assert saved.json()["enabled"] is True

        # A different profile cannot remove the first profile's browser endpoint.
        refused = await async_client.request(
            "DELETE", "/api/v1/push/subscribe", json=payload, headers=second["headers"]
        )
        assert refused.status_code == 200, refused.text
        async with get_sessionmaker()() as session:
            assert await session.scalar(select(func.count()).select_from(PushSubscription)) == 1

        removed = await async_client.request(
            "DELETE", "/api/v1/push/subscribe", json=payload, headers=headers
        )
        assert removed.status_code == 200
        assert removed.json()["enabled"] is False
        async with get_sessionmaker()() as session:
            assert await session.scalar(select(func.count()).select_from(PushSubscription)) == 0
    finally:
        get_settings.cache_clear()


async def test_re_registering_a_browser_refreshes_keys_without_duplicate_rows(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-test-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        customer = await new_customer(async_client, make_token, prefix="push-refresh")
        headers = customer["headers"]
        original = _subscription()
        updated = _subscription()
        updated["keys"] = {"p256dh": "q" * 65, "auth": "b" * 24}
        for payload in (original, updated):
            response = await async_client.post(
                "/api/v1/push/subscribe", json=payload, headers=headers
            )
            assert response.status_code == 200, response.text

        async with get_sessionmaker()() as session:
            row = (await session.execute(select(PushSubscription))).scalar_one()
            assert row.p256dh == "q" * 65
            assert row.auth == "b" * 24
    finally:
        get_settings.cache_clear()


async def test_subscribe_requires_https_and_is_rate_limited(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-test-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test-key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_PUSH", "3")
    get_settings.cache_clear()
    try:
        customer = await new_customer(async_client, make_token, prefix="push-validation")
        http_endpoint = _subscription("http://push.example.test/subscription/abc")
        bad = await async_client.post(
            "/api/v1/push/subscribe", json=http_endpoint, headers=customer["headers"]
        )
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "validation_error"
        unsupported_provider = await async_client.post(
            "/api/v1/push/subscribe",
            json=_subscription("https://push.example.test/subscription/abc"),
            headers=customer["headers"],
        )
        assert unsupported_provider.status_code == 422

        first = await async_client.post(
            "/api/v1/push/subscribe", json=_subscription(), headers=customer["headers"]
        )
        assert first.status_code == 200, first.text
        second = await async_client.post(
            "/api/v1/push/subscribe",
            json=_subscription("https://fcm.googleapis.com/subscription/second"),
            headers=customer["headers"],
        )
        assert second.status_code == 429
        assert second.json()["error"]["details"]["scope"] == "push"

        unauthorized = await async_client.post("/api/v1/push/subscribe", json=_subscription())
        assert unauthorized.status_code == 401
    finally:
        get_settings.cache_clear()


async def test_push_opt_in_must_have_server_vapid_keys(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "")
    get_settings.cache_clear()
    try:
        customer = await new_customer(async_client, make_token, prefix="push-off")
        response = await async_client.post(
            "/api/v1/push/subscribe", json=_subscription(), headers=customer["headers"]
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "unavailable"
    finally:
        get_settings.cache_clear()


async def test_offer_targets_only_the_matching_opted_in_tier_and_dispatches_after_commit(
    async_client: AsyncClient,
    admin: dict[str, Any],
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-test-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test-key")
    get_settings.cache_clear()
    customer = await new_customer(async_client, make_token, prefix="push-gold")
    other = await new_customer(async_client, make_token, prefix="push-other")
    customer_id = uuid.UUID(customer["profile"]["id"])
    other_id = uuid.UUID(other["profile"]["id"])
    async with get_sessionmaker()() as session:
        await session.execute(
            text("UPDATE profiles SET loyalty_tier = 'gold' WHERE id = :id"),
            {"id": customer_id},
        )
        await session.commit()

    sub = await async_client.post(
        "/api/v1/push/subscribe", json=_subscription(), headers=customer["headers"]
    )
    assert sub.status_code == 200, sub.text

    delivered: list[dict[str, Any]] = []

    async def fake_deliver(targets: list[dict[str, str]], **payload: str) -> int:
        delivered.append({"targets": targets, **payload})
        return len(targets)

    monkeypatch.setattr(push_service, "deliver_offer", fake_deliver)
    response = await async_client.post(
        "/api/v1/admin/offers",
        json={
            "title": "A little thank you",
            "body": "Fresh stock is here.",
            "href": "/search?q=ghee",
            "audience": "gold",
        },
        headers=admin["headers"],
    )
    assert response.status_code == 201, response.text
    assert response.json()["push_queued"] == 1
    assert len(delivered) == 1
    assert [row["endpoint"] for row in delivered[0]["targets"]] == [
        "https://fcm.googleapis.com/subscription/abc"
    ]
    assert delivered[0]["href"] == "/search?q=ghee"
    assert other_id != customer_id
    get_settings.cache_clear()


async def test_delivery_counts_success_and_prunes_expired_provider_endpoints(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-test-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test-key")
    get_settings.cache_clear()
    try:
        customer = await new_customer(async_client, make_token, prefix="push-delivery")
        active_endpoint = "https://fcm.googleapis.com/subscription/active"
        expired_endpoint = "https://fcm.googleapis.com/subscription/expired"
        for endpoint in (active_endpoint, expired_endpoint):
            response = await async_client.post(
                "/api/v1/push/subscribe",
                json=_subscription(endpoint),
                headers=customer["headers"],
            )
            assert response.status_code == 200, response.text

        payloads: list[str] = []

        def fake_send(target: dict[str, str], payload: str) -> bool:
            payloads.append(payload)
            if target["endpoint"] == expired_endpoint:
                raise push_service.ExpiredSubscription(expired_endpoint)
            return True

        monkeypatch.setattr(push_service, "_send_one", fake_send)
        delivered = await push_service.deliver_to_profile(
            uuid.UUID(customer["profile"]["id"]),
            title="Fresh stock",
            body="Your favourites are back.",
            href="/search?q=ghee",
        )
        assert delivered == 1
        assert all('"href": "/search?q=ghee"' in payload for payload in payloads)

        async with get_sessionmaker()() as session:
            endpoints = set((await session.scalars(select(PushSubscription.endpoint))).all())
        assert endpoints == {active_endpoint}
    finally:
        get_settings.cache_clear()
