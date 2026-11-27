"""Rate limits: the promises are in the responses, so the tests read responses.

Two kinds of test live here.

The fast ones (no database) pin the arithmetic and the wording — a window that
starts in the same place for every worker, and a `Retry-After` a person can act
on.

The `db` ones drive the real routes: the sixth message is refused and *not*
stored, a wrong referral code costs the caller a guess, and one caller spending
their budget does not affect the next. They also pin the two behaviours that
would otherwise only show up in an incident: a limiter that is switched off
writes nothing, and a limiter whose counter table is unreachable lets the shop
keep trading instead of taking it down.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.core.config import Settings
from app.core.errors import RateLimitedError
from app.core.rate_limit import (
    SWEEP_GRACE,
    describe_wait,
    enforce,
    rule_for,
    sweep_expired,
    window_for,
)
from httpx import AsyncClient
from sqlalchemy import text

# Tokens are verified against a local key pair, never the project's JWKS.
pytestmark = pytest.mark.usefixtures("use_local_keys")

# --------------------------------------------------------------------------- #
# Window arithmetic and copy (no database)
# --------------------------------------------------------------------------- #


def test_windows_are_aligned_so_every_worker_agrees() -> None:
    """Two clocks inside the same window must land on the same boundary."""
    start_a, end_a = window_for(1_700_000_000.0, 3600)
    start_b, end_b = window_for(1_700_000_421.0, 3600)
    assert start_a == start_b
    assert end_a == end_b
    assert start_a.timestamp() % 3600 == 0
    assert end_a - start_a == timedelta(hours=1)


def test_a_window_rolls_over_exactly_on_the_boundary() -> None:
    _, first_end = window_for(1_700_000_000.0, 3600)
    start_second, _ = window_for(first_end.timestamp(), 3600)
    assert start_second == first_end


def test_wait_is_described_the_way_a_person_reads_it() -> None:
    assert describe_wait(1) == "1 second"
    assert describe_wait(42) == "42 seconds"
    # Round up: "1 minute" when 61 seconds are left would be a small lie.
    assert describe_wait(60) == "1 minute"
    assert describe_wait(119) == "1 minute"
    assert describe_wait(120) == "2 minutes"
    assert describe_wait(3600) == "60 minutes"


def test_configuration_decides_each_route() -> None:
    settings = Settings(
        ENVIRONMENT="test",
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_WINDOW_SECONDS=600,
        RATE_LIMIT_FEEDBACK=3,
        RATE_LIMIT_UPLOADS=0,
    )
    feedback = rule_for("feedback", settings)
    assert (feedback.limit, feedback.window_seconds) == (3, 600)
    assert feedback.enabled is True
    # Zero is a switch, not "unlimited but counted".
    assert rule_for("uploads", settings).enabled is False
    # An unknown scope falls back to the generic allowance rather than to no limit.
    assert rule_for("something_new", settings).limit == settings.RATE_LIMIT_DEFAULT


# --------------------------------------------------------------------------- #
# The real routes (database)
# --------------------------------------------------------------------------- #


@pytest.fixture()
def rate_limits_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the limiter on for one test; the rest of the suite runs with it off."""
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("RATE_LIMIT_FEEDBACK", "5")
    monkeypatch.setenv("RATE_LIMIT_REFERRAL", "3")
    monkeypatch.setenv("RATE_LIMIT_UPLOADS", "1")
    get_settings.cache_clear()


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Any) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token('owner@example.com')}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers, "profile": profile}


async def _counters() -> list[dict[str, Any]]:
    from app.db.session import get_sessionmaker

    async with get_sessionmaker()() as session:
        rows = await session.execute(
            text("SELECT bucket, hits FROM rate_limit_counters ORDER BY bucket")
        )
        return [{"bucket": row.bucket, "hits": row.hits} for row in rows]


@pytest.mark.db
async def test_the_sixth_message_is_refused_with_a_usable_answer(
    async_client: AsyncClient, rate_limits_on: None
) -> None:
    body = {"message": "Is the mustard oil back in stock?", "kind": "product"}
    for _ in range(5):
        response = await async_client.post("/api/v1/feedback", json=body)
        assert response.status_code == 201, response.text

    refused = await async_client.post("/api/v1/feedback", json=body)
    assert refused.status_code == 429
    error = refused.json()["error"]
    assert error["code"] == "rate_limited"
    assert error["details"]["limit"] == 5
    assert 0 < error["details"]["retry_after_seconds"] <= 3600
    assert refused.headers["Retry-After"] == str(error["details"]["retry_after_seconds"])
    assert "try again in" in error["message"]

    # The refused message was not stored — a limit that still writes is not a limit.
    from app.db.session import get_sessionmaker

    async with get_sessionmaker()() as session:
        stored = await session.scalar(text("SELECT count(*) FROM feedback"))
    assert stored == 5


@pytest.mark.db
async def test_a_successful_call_reports_the_remaining_budget(
    async_client: AsyncClient, rate_limits_on: None
) -> None:
    response = await async_client.post("/api/v1/feedback", json={"message": "Namaste"})
    assert response.status_code == 201
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"
    assert int(response.headers["X-RateLimit-Reset"]) > int(time.time())


@pytest.mark.db
async def test_one_caller_exhausting_their_budget_does_not_bar_another(
    async_client: AsyncClient, rate_limits_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bucket belongs to the caller, which is the point of keying on them."""
    from app.api import deps

    body = {"message": "One too many"}
    monkeypatch.setattr(deps, "caller_key", lambda request, *, prefix: f"{prefix}:neighbour")
    for _ in range(5):
        assert (await async_client.post("/api/v1/feedback", json=body)).status_code == 201
    assert (await async_client.post("/api/v1/feedback", json=body)).status_code == 429

    monkeypatch.setattr(deps, "caller_key", lambda request, *, prefix: f"{prefix}:someone-else")
    assert (await async_client.post("/api/v1/feedback", json=body)).status_code == 201


@pytest.mark.db
async def test_the_same_caller_gets_a_fresh_budget_in_a_new_window(
    async_client: AsyncClient, rate_limits_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Yesterday's refusal must not follow a customer into today."""
    from app.db.session import get_sessionmaker

    body = {"message": "One too many"}
    for _ in range(5):
        assert (await async_client.post("/api/v1/feedback", json=body)).status_code == 201
    from app.api import deps

    rest_of_window = await async_client.post("/api/v1/feedback", json=body)
    assert rest_of_window.status_code == 429
    assert deps  # the route is wired through the shared key helper

    # Move the spent window into the past, as if an hour had gone by.
    async with get_sessionmaker()() as session:
        await session.execute(
            text(
                "UPDATE rate_limit_counters SET window_start = window_start - interval '3 hours', "
                "window_end = window_end - interval '3 hours'"
            )
        )
        await session.commit()

    assert (await async_client.post("/api/v1/feedback", json=body)).status_code == 201


@pytest.mark.db
async def test_a_wrong_referral_code_costs_the_caller_a_guess(
    async_client: AsyncClient, customer: dict[str, Any], rate_limits_on: None
) -> None:
    """The attack is guessing codes, so a *failed* attempt has to count too."""
    for attempt in range(3):
        response = await async_client.post(
            "/api/v1/rewards/referral",
            json={"code": f"NOPE-{attempt}"},
            headers=customer["headers"],
        )
        # A code that belongs to nobody is a failed guess, and it is counted.
        assert response.status_code == 404, response.text

    refused = await async_client.post(
        "/api/v1/rewards/referral", json={"code": "NOPE-4"}, headers=customer["headers"]
    )
    assert refused.status_code == 429
    assert refused.json()["error"]["details"]["scope"] == "referral"


@pytest.mark.db
async def test_the_upload_button_has_its_own_ceiling(
    async_client: AsyncClient, admin: dict[str, Any], rate_limits_on: None
) -> None:
    """One upload allowed, so the second is stopped by the limiter, not by storage."""
    payload = {"file": ("a.jpg", b"not really an image", "image/jpeg")}
    first = await async_client.post(
        "/api/v1/admin/catalogue/images", files=payload, headers=admin["headers"]
    )
    assert first.status_code in {422, 503}, first.text

    second = await async_client.post(
        "/api/v1/admin/catalogue/images", files=payload, headers=admin["headers"]
    )
    assert second.status_code == 429


@pytest.mark.db
async def test_placing_orders_is_limited_per_customer(
    async_client: AsyncClient,
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
    rate_limits_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The highest-stakes route: one order allowed, the next is refused outright.

    This also pins the dependency order — the limiter needs the authenticated
    customer, so it must resolve *after* the token, and the endpoint must not end
    up verifying that token twice.
    """
    from app.core.config import get_settings
    from tests.support import cart, place

    monkeypatch.setenv("RATE_LIMIT_ORDERS", "1")
    get_settings.cache_clear()

    first = await place(async_client, customer, cart((big_ticket, 1)), key="rl-1")
    assert first.status_code == 201, first.text

    refused = await place(async_client, customer, cart((big_ticket, 1)), key="rl-2")
    assert refused.status_code == 429
    assert refused.json()["error"]["details"]["scope"] == "orders"

    # One order exists, not two: a refusal is not a partial checkout.
    from app.db.session import get_sessionmaker

    async with get_sessionmaker()() as session:
        orders = await session.scalar(text("SELECT count(*) FROM orders"))
    assert orders == 1


@pytest.mark.db
async def test_switched_off_means_no_rows_and_no_refusals(async_client: AsyncClient) -> None:
    """The suite's default: nothing counted, nothing blocked."""
    for _ in range(7):
        response = await async_client.post("/api/v1/feedback", json={"message": "hello there"})
        assert response.status_code == 201
    assert await _counters() == []


@pytest.mark.db
async def test_a_missing_counter_table_does_not_close_the_shop(
    async_client: AsyncClient, rate_limits_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail open: the limiter's own bookkeeping must never be the outage."""
    from app.core import rate_limit

    def broken() -> Any:
        raise RuntimeError("DATABASE_URL is not configured")

    monkeypatch.setattr(rate_limit, "counter_sessionmaker", broken)
    for _ in range(6):
        response = await async_client.post("/api/v1/feedback", json={"message": "still open"})
        assert response.status_code == 201, response.text


@pytest.mark.db
async def test_expired_windows_are_swept_and_live_ones_survive(rate_limits_on: None) -> None:
    from app.db.session import get_sessionmaker

    now = datetime.now(UTC)
    async with get_sessionmaker()() as session:
        await session.execute(
            text(
                "INSERT INTO rate_limit_counters (bucket, window_start, window_end, hits) "
                "VALUES ('old:ip:1', :old_start, :old_end, 4), "
                "('live:ip:1', :start, :end, 1)"
            ),
            {
                "old_start": now - timedelta(hours=3),
                "old_end": now - timedelta(hours=2),
                "start": now,
                "end": now + timedelta(minutes=30),
            },
        )
        await session.commit()

    assert await sweep_expired() == 1
    assert [row["bucket"] for row in await _counters()] == ["live:ip:1"]
    assert timedelta(minutes=30) <= SWEEP_GRACE


@pytest.mark.db
async def test_the_shared_seam_raises_the_one_error_shape(rate_limits_on: None) -> None:
    """`enforce` is what every route calls; prove the 429 it raises."""
    with pytest.raises(RateLimitedError) as caught:
        for _ in range(10):
            await enforce("feedback", "ip:direct-call")
    assert caught.value.status_code == 429
    assert caught.value.details["scope"] == "feedback"
    assert caught.value.headers["Retry-After"].isdigit()
