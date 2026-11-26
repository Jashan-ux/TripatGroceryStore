"""Phase 6: the owner's numbers, and whether they can be trusted.

The acceptance criteria this file exists for:

* **A-10** — analytics cards drill down, an empty range is safe, and the figures
  reconcile. "Reconcile" is asserted literally: the revenue on the card equals
  ``total_paise`` of the listing the card opens, and equals the sum of the rows
  when they fit on one page. A dashboard whose card and drill-down disagree is
  worse than no dashboard.
* **A-11** — a low-stock row knows where its fix lives. The API hands back the
  admin route that opens that product's edit dialog, and the test follows it.
* **A-13** — customers list with a tier filter, a profile with past orders, and a
  top-customer flag that means the top three by lifetime spend.

One more thing is pinned here because it is invisible until it is wrong: **a day
is a Haryana day.** An order placed at 23:40 IST belongs to that evening's
turnover, even though UTC has already rolled over.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import cart, new_customer, place

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers, "profile": profile}


def _shop_today() -> date:
    return (datetime.now(UTC) + timedelta(hours=5, minutes=30)).date()


async def _set_placed_at(order_id: str, iso_utc: datetime) -> None:
    """Move an order in time, so a test can talk about a specific shop-day."""
    async with get_sessionmaker()() as session:
        await session.execute(
            text("UPDATE orders SET placed_at = :ts WHERE id = :id"),
            {"ts": iso_utc, "id": uuid.UUID(order_id)},
        )
        await session.commit()


async def _one_order(
    async_client: AsyncClient,
    customer: dict[str, Any],
    product: dict[str, Any],
    *,
    key: str,
    quantity: int = 1,
) -> dict[str, Any]:
    placed = await place(async_client, customer, cart((product, quantity)), key=key)
    assert placed.status_code == 201, placed.text
    return placed.json()


# --------------------------------------------------------------------------- #
# A-10 — the cards, the drill-down, and the arithmetic between them
# --------------------------------------------------------------------------- #


async def test_a_quiet_range_answers_zeros_instead_of_an_error(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    """No orders is a normal day off, not a 500 and not a null."""
    response = await async_client.get(
        "/api/v1/admin/analytics/summary",
        params={"from_date": "2020-01-01", "to_date": "2020-01-31"},
        headers=admin["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revenue_paise"] == 0
    assert body["orders"] == 0
    assert body["average_order_paise"] == 0
    assert body["repeat_rate_percent"] == 0
    assert body["by_status"] == {}
    assert body["range"]["days"] == 31
    assert body["range"]["timezone"] == "Asia/Kolkata"

    series = await async_client.get(
        "/api/v1/admin/analytics/series",
        params={"from_date": "2020-01-01", "to_date": "2020-01-31"},
        headers=admin["headers"],
    )
    assert series.status_code == 200
    points = series.json()["points"]
    assert len(points) == 31, "every day in the range must appear, zero or not"
    assert {point["orders"] for point in points} == {0}

    drill = await async_client.get(
        "/api/v1/admin/analytics/orders",
        params={"from_date": "2020-01-01", "to_date": "2020-01-31"},
        headers=admin["headers"],
    )
    assert drill.status_code == 200
    assert drill.json()["items"] == []
    assert drill.json()["total"] == 0
    assert drill.json()["total_paise"] == 0


async def test_the_card_equals_the_rows_it_opens(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
) -> None:
    """The number on the card and the list underneath it are one query."""
    first = await _one_order(async_client, customer, big_ticket, key="an-1")
    second = await _one_order(async_client, customer, big_ticket, key="an-2")

    params = {"from_date": str(_shop_today()), "to_date": str(_shop_today())}
    summary = (
        await async_client.get(
            "/api/v1/admin/analytics/summary", params=params, headers=admin["headers"]
        )
    ).json()
    drill = (
        await async_client.get(
            "/api/v1/admin/analytics/orders", params=params, headers=admin["headers"]
        )
    ).json()

    assert summary["orders"] == 2
    assert summary["revenue_paise"] == first["total_paise"] + second["total_paise"]
    # The card, the listing total, and the rows themselves must all agree.
    assert drill["total"] == summary["orders"]
    assert drill["total_paise"] == summary["revenue_paise"]
    assert sum(row["total_paise"] for row in drill["items"]) == summary["revenue_paise"]
    assert summary["average_order_paise"] == summary["revenue_paise"] // 2
    assert summary["items_sold"] == 2

    series = (
        await async_client.get(
            "/api/v1/admin/analytics/series", params=params, headers=admin["headers"]
        )
    ).json()
    assert series["points"][-1]["revenue_paise"] == summary["revenue_paise"]
    assert series["points"][-1]["orders"] == 2


async def test_a_cancelled_order_is_not_income_but_is_still_visible(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
) -> None:
    """Turnover excludes it; the status breakdown still tells the truth."""
    kept = await _one_order(async_client, customer, big_ticket, key="an-c1")
    gone = await _one_order(async_client, customer, big_ticket, key="an-c2")
    cancelled = await async_client.post(
        f"/api/v1/orders/{gone['id']}/cancel", headers=customer["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text

    params = {"from_date": str(_shop_today()), "to_date": str(_shop_today())}
    summary = (
        await async_client.get(
            "/api/v1/admin/analytics/summary", params=params, headers=admin["headers"]
        )
    ).json()
    assert summary["revenue_paise"] == kept["total_paise"]
    assert summary["orders"] == 1
    assert summary["by_status"]["cancelled"] == 1
    assert summary["by_status"]["processing"] == 1

    only_cancelled = await async_client.get(
        "/api/v1/admin/analytics/orders",
        params={**params, "status": "cancelled"},
        headers=admin["headers"],
    )
    assert only_cancelled.status_code == 200
    # The drill-down applies the same revenue predicate, so a cancelled-only
    # filter is legitimately empty rather than quietly counting refunded money.
    assert only_cancelled.json()["total"] == 0


async def test_repeat_and_new_customers_are_counted_once_each(
    async_client: AsyncClient,
    admin: dict[str, Any],
    make_token: Callable[..., str],
    big_ticket: dict[str, Any],
) -> None:
    regular = await new_customer(async_client, make_token)
    one_timer = await new_customer(async_client, make_token, prefix="other")
    await _one_order(async_client, regular, big_ticket, key="an-r1")
    await _one_order(async_client, regular, big_ticket, key="an-r2")
    await _one_order(async_client, one_timer, big_ticket, key="an-t1")

    params = {"from_date": str(_shop_today()), "to_date": str(_shop_today())}
    summary = (
        await async_client.get(
            "/api/v1/admin/analytics/summary", params=params, headers=admin["headers"]
        )
    ).json()
    assert summary["repeat_customers"] == 1
    assert summary["new_customers"] == 2  # both placed their first order today
    assert summary["repeat_rate_percent"] == 50  # 1 repeat of 2 customers


async def test_a_late_evening_order_belongs_to_that_evening(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
) -> None:
    """23:40 IST is still today, even though UTC already says tomorrow."""
    order = await _one_order(async_client, customer, big_ticket, key="an-late")
    today = _shop_today()
    await _set_placed_at(
        order["id"],
        datetime.combine(today, datetime.min.time(), UTC) + timedelta(hours=18, minutes=10),
    )

    params = {"from_date": str(today), "to_date": str(today)}
    summary = (
        await async_client.get(
            "/api/v1/admin/analytics/summary", params=params, headers=admin["headers"]
        )
    ).json()
    assert summary["orders"] == 1, "the order must land on the IST date it was placed"

    tomorrow = today + timedelta(days=1)
    next_day = (
        await async_client.get(
            "/api/v1/admin/analytics/summary",
            params={"from_date": str(tomorrow), "to_date": str(tomorrow)},
            headers=admin["headers"],
        )
    ).json()
    assert next_day["orders"] == 0


async def test_a_nonsense_range_is_clamped_rather_than_refused(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    """An owner tapping a date picker should not be told off by a 422."""
    backwards = await async_client.get(
        "/api/v1/admin/analytics/summary",
        params={"from_date": "2026-02-01", "to_date": "2026-01-01"},
        headers=admin["headers"],
    )
    assert backwards.status_code == 200
    assert backwards.json()["range"]["from_date"] == "2026-01-01"
    assert backwards.json()["range"]["to_date"] == "2026-02-01"

    everything = await async_client.get(
        "/api/v1/admin/analytics/summary",
        params={"from_date": "2000-01-01", "to_date": "2030-01-01"},
        headers=admin["headers"],
    )
    assert everything.status_code == 200
    assert everything.json()["range"]["days"] <= 366

    defaults = await async_client.get("/api/v1/admin/analytics/summary", headers=admin["headers"])
    assert defaults.status_code == 200
    assert defaults.json()["range"]["days"] == 30


async def test_what_sold_adds_up_to_the_parts(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
    products: dict[str, Any],
) -> None:
    await _one_order(async_client, customer, big_ticket, key="an-p1")
    ghee = products["ghee"]
    await _one_order(async_client, customer, ghee, key="an-p2", quantity=2)

    params = {"from_date": str(_shop_today()), "to_date": str(_shop_today())}
    sold = (
        await async_client.get(
            "/api/v1/admin/analytics/products", params=params, headers=admin["headers"]
        )
    ).json()
    assert sold["total_revenue_paise"] == sum(row["revenue_paise"] for row in sold["items"])
    assert sold["total_units"] == sum(row["units"] for row in sold["items"])
    top = sold["items"][0]
    assert top["units"] >= 2  # the ghee, ordered twice in one line
    assert sold["range"]["days"] == 1


# --------------------------------------------------------------------------- #
# A-11 — a row that knows where it is fixed
# --------------------------------------------------------------------------- #


async def test_a_low_stock_row_points_at_its_own_edit_dialog(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    async with get_sessionmaker()() as session:
        ghee_id = await session.scalar(
            text("SELECT id FROM products WHERE slug = :slug"), {"slug": catalogue["ghee_slug"]}
        )
        await session.execute(
            text("UPDATE products SET stock = 0, low_stock_threshold = 3 WHERE id = :id"),
            {"id": ghee_id},
        )
        await session.commit()

    response = await async_client.get("/api/v1/admin/analytics/low-stock", headers=admin["headers"])
    assert response.status_code == 200
    rows = {row["product_id"]: row for row in response.json()["items"]}
    assert str(ghee_id) in rows
    row = rows[str(ghee_id)]
    assert row["stock"] == 0 and row["threshold"] == 3
    assert row["edit_href"] == f"/admin/products?edit={ghee_id}"

    # The same count the dashboard card shows.
    summary = await async_client.get("/api/v1/admin/analytics/summary", headers=admin["headers"])
    before = summary.json()["low_stock"]
    assert before == len(rows)

    # The destination is a real edit, not a dead-end detail page: the same stock
    # edit the dialog makes removes the product from the card on its next read.
    saved = await async_client.patch(
        f"/api/v1/admin/catalogue/products/{ghee_id}",
        json={"stock": 25},
        headers=admin["headers"],
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["stock"] == 25
    refreshed = await async_client.get("/api/v1/admin/analytics/summary", headers=admin["headers"])
    assert refreshed.json()["low_stock"] == before - 1


# --------------------------------------------------------------------------- #
# A-13 — customers, tiers, profiles
# --------------------------------------------------------------------------- #


async def test_customers_list_their_tier_and_can_be_filtered(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
) -> None:
    await _one_order(async_client, customer, big_ticket, key="an-tier")
    async with get_sessionmaker()() as session:
        await session.execute(
            text("UPDATE profiles SET loyalty_tier = 'gold' WHERE id = :id"),
            {"id": uuid.UUID(customer["profile"]["id"])},
        )
        await session.commit()

    listing = await async_client.get(
        "/api/v1/admin/customers", params={"tier": "gold"}, headers=admin["headers"]
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert [row["id"] for row in body["items"]] == [customer["profile"]["id"]]
    row = body["items"][0]
    assert row["tier"] == "gold"
    assert row["orders"] == 1
    assert row["last_order_at"] is not None
    assert body["counts"].get("gold") == 1

    empty = await async_client.get(
        "/api/v1/admin/customers", params={"tier": "diamond"}, headers=admin["headers"]
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []


async def test_a_customer_can_be_found_by_phone_or_email(
    async_client: AsyncClient, admin: dict[str, Any], customer: dict[str, Any]
) -> None:
    by_phone = await async_client.get(
        "/api/v1/admin/customers",
        params={"q": customer["phone"][-6:]},
        headers=admin["headers"],
    )
    assert by_phone.status_code == 200
    assert customer["profile"]["id"] in [row["id"] for row in by_phone.json()["items"]]

    by_email = await async_client.get(
        "/api/v1/admin/customers",
        params={"q": customer["profile"]["email"]},
        headers=admin["headers"],
    )
    assert [row["id"] for row in by_email.json()["items"]] == [customer["profile"]["id"]]


async def test_a_profile_shows_every_past_order_and_the_average(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    big_ticket: dict[str, Any],
) -> None:
    first = await _one_order(async_client, customer, big_ticket, key="an-prof1")
    second = await _one_order(async_client, customer, big_ticket, key="an-prof2")

    response = await async_client.get(
        f"/api/v1/admin/customers/{customer['profile']['id']}", headers=admin["headers"]
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["orders"] == 2
    assert [order["id"] for order in body["recent_orders"]] == [second["id"], first["id"]]
    assert body["average_order_paise"] == body["lifetime_spend_paise"] // 2
    assert body["addresses"] == 1
    assert body["first_order_at"] is not None


async def test_the_top_customer_flag_means_the_top_three(
    async_client: AsyncClient,
    admin: dict[str, Any],
    make_token: Callable[..., str],
) -> None:
    customers = [
        await new_customer(async_client, make_token, prefix=f"top-{rank}") for rank in range(1, 5)
    ]

    # Spend accrues when an order is *delivered* (cash in hand); seed the ledger
    # values directly so this test isolates global ranking and the top-three cutoff.
    spends = (400_000, 300_000, 200_000, 100_000)
    async with get_sessionmaker()() as session:
        for customer, spend in zip(customers, spends, strict=True):
            await session.execute(
                text("UPDATE profiles SET lifetime_spend_paise = :spend WHERE id = :id"),
                {"spend": spend, "id": uuid.UUID(customer["profile"]["id"])},
            )
        await session.commit()

    listing = (await async_client.get("/api/v1/admin/customers", headers=admin["headers"])).json()
    rows = {row["id"]: row for row in listing["items"]}
    assert [rows[customer["profile"]["id"]]["is_top"] for customer in customers] == [
        True,
        True,
        True,
        False,
    ]
    # Spenders are ordered highest first, and the fourth customer is outside rank 3.
    listed_spends = [row["lifetime_spend_paise"] for row in listing["items"]]
    assert listed_spends[:4] == list(spends)


async def test_an_unknown_customer_is_a_clean_404(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await async_client.get(
        f"/api/v1/admin/customers/{uuid.uuid4()}", headers=admin["headers"]
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


async def test_analytics_are_owner_only(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    for path in (
        "/api/v1/admin/analytics/summary",
        "/api/v1/admin/analytics/series",
        "/api/v1/admin/analytics/orders",
        "/api/v1/admin/analytics/products",
        "/api/v1/admin/analytics/low-stock",
        "/api/v1/admin/customers",
    ):
        response = await async_client.get(path, headers=customer["headers"])
        assert response.status_code == 403, f"{path} leaked to a customer"
        assert response.json()["error"]["code"] == "admin_only"
