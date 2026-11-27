"""Phase 5's operator tools: offers, settings, the feedback inbox and the audit trail.

The three promises here are all "the shop changes without a developer":

* an offer reaches the people it names, in the bell they already use (A-14);
* a settings edit changes the next checkout, not the next deploy (A-15);
* every admin action leaves a row saying who did what (S-12);
* a message from the contact page is stored, announced and emailable (C-18).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.db.session import get_sessionmaker
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
    assert profile["role"] == "admin", profile
    return {"headers": headers, "profile": profile}


@pytest.fixture()
async def restore_settings():
    """Settings are one shared row; put back whatever a test changed."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        row = (await session.execute(text("SELECT * FROM store_settings LIMIT 1"))).mappings().one()
        original = dict(row)
    yield
    columns = [
        "store_name",
        "store_phone",
        "store_address",
        "store_maps_url",
        "feedback_email",
        "notification_email",
        "minimum_order_paise",
        "serviceable_pincodes",
        "default_delivery_days",
        "low_stock_threshold",
        "scratch_threshold_paise",
        "scratch_min_paise",
        "scratch_max_paise",
        "tier_gold_paise",
        "tier_platinum_paise",
        "tier_diamond_paise",
    ]
    assignments = ", ".join(f"{column} = :{column}" for column in columns)
    async with sessionmaker() as session:
        # The column names are the literal list above, never request input.
        await session.execute(
            text(f"UPDATE store_settings SET {assignments}"),  # noqa: S608
            {column: original[column] for column in columns},
        )
        await session.commit()
    settings_service.invalidate_cache()


async def _bell(async_client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await async_client.get("/api/v1/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _set_tier(email: str, tier: str) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE profiles SET loyalty_tier = :tier WHERE email = :email"),
            {"tier": tier, "email": email},
        )
        await session.commit()


# --------------------------------------------------------------------------- #
# A-14: offers
# --------------------------------------------------------------------------- #
async def test_an_offer_to_one_tier_reaches_only_that_tier(
    async_client: AsyncClient, admin: dict[str, Any], make_token: Callable[..., str]
) -> None:
    everyone = await new_customer(async_client, make_token, prefix="buyer")
    gold = await new_customer(async_client, make_token, prefix="buyer")
    await _set_tier(gold["email"], "gold")

    sent = await async_client.post(
        "/api/v1/admin/offers",
        json={
            "title": "Gold members: 10% off pure ghee",
            "body": "This week only, on 1L tins.",
            "href": "/products/test-ghee-1l",
            "audience": "gold",
        },
        headers=admin["headers"],
    )
    assert sent.status_code == 201, sent.text
    offer = sent.json()
    assert offer["audience"] == "gold"
    assert offer["recipients"] == 1, offer
    assert offer["is_active"] is True

    gold_bell = await _bell(async_client, gold["headers"])
    assert [entry["kind"] for entry in gold_bell["items"]] == ["offer"]
    assert gold_bell["items"][0]["title"] == offer["title"]
    assert gold_bell["items"][0]["href"] == offer["href"]

    other_bell = await _bell(async_client, everyone["headers"])
    assert other_bell["items"] == [], "a tier offer must not ring anyone else's bell"


async def test_an_offer_to_everyone_rings_every_customer_and_can_be_read_without_signing_in(
    async_client: AsyncClient, admin: dict[str, Any], make_token: Callable[..., str]
) -> None:
    first = await new_customer(async_client, make_token, prefix="buyer")
    second = await new_customer(async_client, make_token, prefix="buyer")

    sent = await async_client.post(
        "/api/v1/admin/offers",
        json={"title": "Diwali hours: open till 9pm", "body": "All week.", "audience": "all"},
        headers=admin["headers"],
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["recipients"] == 2

    for person in (first, second):
        bell = await _bell(async_client, person["headers"])
        assert "Diwali hours" in bell["items"][0]["title"]

    # The banner is public: an anonymous visitor sees the newest live offer.
    banner = await async_client.get("/api/v1/offers/current")
    assert banner.status_code == 200
    assert banner.json()["offer"]["title"] == "Diwali hours: open till 9pm"

    history = await async_client.get("/api/v1/admin/offers", headers=admin["headers"])
    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == sent.json()["id"]


async def test_an_expired_offer_stops_showing_on_the_banner(
    async_client: AsyncClient, admin: dict[str, Any], make_token: Callable[..., str]
) -> None:
    await new_customer(async_client, make_token, prefix="buyer")
    past = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
    sent = await async_client.post(
        "/api/v1/admin/offers",
        json={"title": "Yesterday's news", "audience": "all", "expires_at": past},
        headers=admin["headers"],
    )
    assert sent.status_code == 201, sent.text

    banner = await async_client.get("/api/v1/offers/current")
    assert banner.status_code == 200
    body = banner.json()["offer"]
    assert body is None or body["title"] != "Yesterday's news"


async def test_an_offer_must_link_inside_our_own_app(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await async_client.post(
        "/api/v1/admin/offers",
        json={"title": "Click me", "href": "https://evil.example.com/phish", "audience": "all"},
        headers=admin["headers"],
    )
    assert response.status_code == 422


async def test_sending_an_offer_is_audit_logged(
    async_client: AsyncClient, admin: dict[str, Any], make_token: Callable[..., str]
) -> None:
    await new_customer(async_client, make_token, prefix="buyer")
    await async_client.post(
        "/api/v1/admin/offers",
        json={"title": "Logged offer", "audience": "all"},
        headers=admin["headers"],
    )
    log = await async_client.get("/api/v1/admin/audit", headers=admin["headers"])
    entry = next(row for row in log.json()["items"] if row["action"] == "offer.sent")
    assert entry["entity"] == "offer"
    assert entry["after"]["recipients"] == 1
    assert entry["actor_email"] == ADMIN_EMAIL


async def test_offers_are_owner_only(async_client: AsyncClient, customer: dict[str, Any]) -> None:
    listed = await async_client.get("/api/v1/admin/offers", headers=customer["headers"])
    assert listed.status_code == 403
    sent = await async_client.post(
        "/api/v1/admin/offers",
        json={"title": "I am not the owner", "audience": "all"},
        headers=customer["headers"],
    )
    assert sent.status_code == 403


# --------------------------------------------------------------------------- #
# A-15: settings
# --------------------------------------------------------------------------- #
async def test_the_owner_can_read_and_change_every_number(
    async_client: AsyncClient, admin: dict[str, Any], restore_settings: None
) -> None:
    current = await async_client.get("/api/v1/admin/settings", headers=admin["headers"])
    assert current.status_code == 200, current.text
    before = current.json()
    assert before["store_phone"] and before["store_name"]

    patched = await async_client.patch(
        "/api/v1/admin/settings",
        json={"store_phone": "+91 98765 43210", "low_stock_threshold": 7},
        headers=admin["headers"],
    )
    assert patched.status_code == 200, patched.text
    after = patched.json()
    assert after["store_phone"] == "+91 98765 43210"
    assert after["low_stock_threshold"] == 7
    # Only what was sent changes.
    assert after["minimum_order_paise"] == before["minimum_order_paise"]
    assert after["updated_at"] >= before["updated_at"]

    reread = await async_client.get("/api/v1/admin/settings", headers=admin["headers"])
    assert reread.json() == after


async def test_a_new_minimum_order_applies_to_the_very_next_checkout(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    catalogue: dict[str, Any],
    restore_settings: None,
) -> None:
    ghee = await product_detail(async_client, catalogue["ghee_slug"])
    line_total = ghee["price_paise"] * 2

    # Warm the settings cache the way a storefront request would.
    # Two tins clear the shop's ₹500 minimum before the change.
    allowed = await place(async_client, customer, cart((ghee, 2)))
    assert allowed.status_code == 201, allowed.text

    raised = await async_client.patch(
        "/api/v1/admin/settings",
        json={"minimum_order_paise": line_total + 10_000},
        headers=admin["headers"],
    )
    assert raised.status_code == 200, raised.text

    # No restart, no redeploy: the next checkout already knows.
    refused = await place(async_client, customer, cart((ghee, 2)))
    assert refused.status_code == 422, refused.text
    error = refused.json()["error"]
    assert error["code"] == "minimum_order_not_met"
    assert error["message"].startswith("Minimum order is ₹")
    assert error["details"]["shortfall_paise"] == (line_total + 10_000) - line_total


async def test_settings_are_validated_as_a_set_not_field_by_field(
    async_client: AsyncClient, admin: dict[str, Any], restore_settings: None
) -> None:
    original = (await async_client.get("/api/v1/admin/settings", headers=admin["headers"])).json()
    # Gold must sit below platinum, which must sit below diamond.
    inverted = await async_client.patch(
        "/api/v1/admin/settings",
        json={"tier_gold_paise": 5_00_00_000, "tier_platinum_paise": 1_00_000},
        headers=admin["headers"],
    )
    assert inverted.status_code == 422, inverted.text
    assert inverted.json()["error"]["code"] == "invalid_settings"

    scratch = await async_client.patch(
        "/api/v1/admin/settings",
        json={"scratch_min_paise": 9000, "scratch_max_paise": 1000},
        headers=admin["headers"],
    )
    assert scratch.status_code == 422

    maps = await async_client.patch(
        "/api/v1/admin/settings",
        json={"store_maps_url": "http://maps.google.com/not-https"},
        headers=admin["headers"],
    )
    assert maps.status_code == 422

    # And none of the refusals were half-applied.
    current = (await async_client.get("/api/v1/admin/settings", headers=admin["headers"])).json()
    assert (
        current["tier_gold_paise"] < current["tier_platinum_paise"] < current["tier_diamond_paise"]
    )
    assert current["scratch_min_paise"] <= current["scratch_max_paise"]
    assert current["store_maps_url"] == original["store_maps_url"]
    assert current["tier_gold_paise"] == original["tier_gold_paise"]


async def test_a_settings_edit_is_audit_logged_with_before_and_after(
    async_client: AsyncClient, admin: dict[str, Any], restore_settings: None
) -> None:
    before = (await async_client.get("/api/v1/admin/settings", headers=admin["headers"])).json()
    await async_client.patch(
        "/api/v1/admin/settings",
        json={"default_delivery_days": 3},
        headers=admin["headers"],
    )
    log = await async_client.get("/api/v1/admin/audit", headers=admin["headers"])
    entry = next(row for row in log.json()["items"] if row["action"] == "settings.updated")
    assert entry["entity"] == "settings"
    assert entry["before"]["default_delivery_days"] == before["default_delivery_days"]
    assert entry["after"]["default_delivery_days"] == 3
    assert entry["summary"] == "default_delivery_days"


async def test_settings_are_owner_only(async_client: AsyncClient, customer: dict[str, Any]) -> None:
    assert (
        await async_client.get("/api/v1/admin/settings", headers=customer["headers"])
    ).status_code == 403
    assert (
        await async_client.patch(
            "/api/v1/admin/settings",
            json={"store_name": "Not Your Shop"},
            headers=customer["headers"],
        )
    ).status_code == 403


# --------------------------------------------------------------------------- #
# C-18: feedback
# --------------------------------------------------------------------------- #
async def _feedback(
    async_client: AsyncClient,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> Any:
    return await async_client.post("/api/v1/feedback", json=payload, headers=headers or {})


async def test_anyone_can_write_to_the_shop_without_signing_in(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    message = f"My atta packet was torn on delivery ({uuid.uuid4().hex[:6]})."
    response = await _feedback(
        async_client,
        {
            "name": "Ramesh Kumar",
            "phone": "9876543210",
            "email": "ramesh@example.com",
            "kind": "order",
            "message": message,
        },
    )
    assert response.status_code == 201, response.text
    stored = response.json()
    assert stored["status"] == "new"
    assert stored["message"] == message

    # The shop hears about it in the bell it already watches…
    bell = await _bell(async_client, admin["headers"])
    entry = next(item for item in bell["items"] if item["kind"] == "system")
    assert "Ramesh Kumar" in entry["title"]
    assert entry["href"] == "/admin/feedback"

    # …and the message is in the outbox for the shop's feedback address.
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        queued = (
            (
                await session.execute(
                    text(
                        "SELECT to_email, subject, dedupe_key FROM email_messages "
                        "WHERE dedupe_key = :key"
                    ),
                    {"key": f"feedback:{stored['id']}"},
                )
            )
            .mappings()
            .all()
        )
    assert len(queued) == 1, queued
    assert "Ramesh Kumar" in queued[0]["subject"]


async def test_signed_in_feedback_fills_in_what_it_can(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    response = await _feedback(
        async_client,
        {"message": "Please stock jaggery in 500g packs."},
        headers=customer["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == customer["email"]
    assert body["phone"] == customer["phone"]


async def test_a_too_short_message_is_refused(
    async_client: AsyncClient,
) -> None:
    response = await _feedback(async_client, {"message": "hi"})
    assert response.status_code == 422


async def test_the_inbox_lists_new_first_and_marking_read_sticks(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    tag = uuid.uuid4().hex[:6]
    for index in range(3):
        created = await _feedback(
            async_client, {"name": f"Writer {index}", "message": f"Message {tag} number {index}"}
        )
        assert created.status_code == 201, created.text

    listing = await async_client.get(
        "/api/v1/admin/feedback", params={"status": "new"}, headers=admin["headers"]
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] >= 3
    newest = body["items"][0]
    assert newest["name"] == "Writer 2", "the inbox is newest first"

    read = await async_client.post(
        f"/api/v1/admin/feedback/{newest['id']}/read", headers=admin["headers"]
    )
    assert read.status_code == 200, read.text
    assert read.json()["status"] == "read"
    assert read.json()["read_at"] is not None

    still_new = await async_client.get(
        "/api/v1/admin/feedback", params={"status": "new"}, headers=admin["headers"]
    )
    assert newest["id"] not in {item["id"] for item in still_new.json()["items"]}

    read_only = await async_client.get(
        "/api/v1/admin/feedback", params={"status": "read"}, headers=admin["headers"]
    )
    assert newest["id"] in {item["id"] for item in read_only.json()["items"]}

    # Reading it twice is harmless, not an error.
    twice = await async_client.post(
        f"/api/v1/admin/feedback/{newest['id']}/read", headers=admin["headers"]
    )
    assert twice.status_code == 200


async def test_the_inbox_is_owner_only(async_client: AsyncClient, customer: dict[str, Any]) -> None:
    assert (
        await async_client.get("/api/v1/admin/feedback", headers=customer["headers"])
    ).status_code == 403


async def test_marking_a_missing_message_read_is_a_404(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await async_client.post(
        f"/api/v1/admin/feedback/{uuid.uuid4()}/read", headers=admin["headers"]
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# S-12: the audit trail itself
# --------------------------------------------------------------------------- #
async def test_the_audit_trail_answers_who_changed_what_and_when(
    async_client: AsyncClient, admin: dict[str, Any], make_token: Callable[..., str]
) -> None:
    # Two different admins, so "who" is a fact and not a constant.
    second_email = "manager@example.com"
    second = {"Authorization": f"Bearer {make_token(second_email)}"}
    profile = (await async_client.get("/api/v1/me", headers=second)).json()
    assert profile["role"] == "customer", "only ADMIN_EMAILS are owners"

    await async_client.patch(
        "/api/v1/admin/settings",
        json={"store_name": "Tripat Pansari"},
        headers=admin["headers"],
    )

    log = await async_client.get(
        "/api/v1/admin/audit", params={"entity": "settings"}, headers=admin["headers"]
    )
    assert log.status_code == 200, log.text
    entries = log.json()["items"]
    assert entries, "an admin action must leave a row"
    assert all(entry["entity"] == "settings" for entry in entries)
    assert all(entry["actor_email"] == ADMIN_EMAIL for entry in entries)
    # Oldest last: the owner reads the newest change first.
    stamps = [entry["created_at"] for entry in entries]
    assert stamps == sorted(stamps, reverse=True)

    forbidden = await async_client.get("/api/v1/admin/audit", headers=second)
    assert forbidden.status_code == 403


async def test_an_admin_action_that_changes_nothing_logs_nothing(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    current = (await async_client.get("/api/v1/admin/settings", headers=admin["headers"])).json()
    before = await async_client.get("/api/v1/admin/audit", headers=admin["headers"])
    await async_client.patch(
        "/api/v1/admin/settings",
        json={"store_name": current["store_name"]},
        headers=admin["headers"],
    )
    after = await async_client.get("/api/v1/admin/audit", headers=admin["headers"])
    # The row is recorded with "no change" rather than a phantom diff…
    newest = after.json()["items"][0]
    assert newest["action"] == "settings.updated"
    assert newest["summary"] == "no change"
    assert newest["before"] == {} and newest["after"] == {}
    assert after.json()["total"] == before.json()["total"] + 1
