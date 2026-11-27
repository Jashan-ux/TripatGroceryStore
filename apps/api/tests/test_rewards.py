"""Database-backed tests for Phase 4: wallet, referrals, scratch cards, returns, badges.

The money rules the brief is strict about, each one asserted against a real
Postgres:

* the ledger adds up (``wallets.balance_paise == sum(delta_paise)``);
* the wallet can never go below zero, and never covers more than the order;
* the friend's discount is on the first order only, the referrer is paid only after
  that order is *delivered*, and nobody can refer themselves;
* a card pays once, after delivery, and the amount is never in the response before
  the reveal;
* a return pays nothing until the shop has the goods, then pays exactly once;
* a delivered order earns a badge, and a return takes the spend back.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import cart, new_customer, place, product_detail, stock_of

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers, "profile": profile}


@pytest.fixture()
async def ghee(async_client: AsyncClient, catalogue: dict[str, Any]) -> dict[str, Any]:
    return await product_detail(async_client, catalogue["ghee_slug"])


async def _wallet(async_client: AsyncClient, who: dict[str, Any]) -> dict[str, Any]:
    response = await async_client.get("/api/v1/rewards/wallet", headers=who["headers"])
    assert response.status_code == 200, response.text
    return response.json()


async def _summary(async_client: AsyncClient, who: dict[str, Any]) -> dict[str, Any]:
    response = await async_client.get("/api/v1/rewards", headers=who["headers"])
    assert response.status_code == 200, response.text
    return response.json()


async def _place(
    async_client: AsyncClient,
    who: dict[str, Any],
    *lines: tuple[dict[str, Any], int],
    use_wallet_paise: int = 0,
) -> dict[str, Any]:
    response = await place(
        async_client, who, {**cart(*lines), "use_wallet_paise": use_wallet_paise}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _deliver(async_client: AsyncClient, admin: dict[str, Any], order: dict[str, Any]) -> None:
    for status in ("shipped", "out_for_delivery", "delivered"):
        moved = await async_client.post(
            f"/api/v1/admin/orders/{order['id']}/status",
            json={"status": status},
            headers=admin["headers"],
        )
        assert moved.status_code == 200, moved.text


async def give_wallet(profile_id: str, amount_paise: int, note: str = "Test credit") -> None:
    """Seed a wallet directly.

    Used where the *wallet spend* is what is on trial: the earning paths (cards,
    referrals, refunds) are exercised by their own tests, so this keeps them from
    having to succeed before a wallet test can run.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        wallet_id = await session.scalar(
            text(
                "insert into wallets (profile_id, balance_paise) values (:profile_id, :amount) "
                "on conflict (profile_id) do update set balance_paise = wallets.balance_paise "
                "+ :amount returning id"
            ),
            {"profile_id": profile_id, "amount": amount_paise},
        )
        balance = await session.scalar(
            text("select balance_paise from wallets where id = :id"), {"id": wallet_id}
        )
        await session.execute(
            text(
                "insert into wallet_entries (wallet_id, delta_paise, balance_after_paise, "
                "reason, note) values (:wallet_id, :delta, :after, 'adjustment', :note)"
            ),
            {
                "wallet_id": wallet_id,
                "delta": amount_paise,
                "after": balance,
                "note": note,
            },
        )
        await session.commit()


async def ledger_sum(profile_id: str) -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return int(
            await session.scalar(
                text(
                    "select coalesce(sum(e.delta_paise), 0) from wallet_entries e "
                    "join wallets w on w.id = e.wallet_id where w.profile_id = :profile_id"
                ),
                {"profile_id": profile_id},
            )
            or 0
        )


#: The only settings a test may move, so the SQL below never interpolates a caller's string.
SETTABLE = {"tier_gold_paise", "tier_platinum_paise", "tier_diamond_paise", "return_window_days"}


async def set_settings(**values: Any) -> None:
    unknown = set(values) - SETTABLE
    assert not unknown, f"refusing to set {unknown}"
    sessionmaker = get_sessionmaker()
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    async with sessionmaker() as session:
        await session.execute(
            text(f"update store_settings set {assignments} where id = 1"),  # noqa: S608
            values,
        )
        await session.commit()
    from app.services import settings as settings_service

    settings_service.invalidate_cache()


# --------------------------------------------------------------------------- #
# Wallet
# --------------------------------------------------------------------------- #
async def test_a_new_customer_has_an_empty_wallet(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    statement = await _wallet(async_client, customer)
    assert statement["balance_paise"] == 0
    assert statement["entries"] == []
    assert statement["total"] == 0

    anonymous = await async_client.get("/api/v1/rewards/wallet")
    assert anonymous.status_code == 401


async def test_the_wallet_pays_part_of_an_order_and_the_rest_is_cash(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    await give_wallet(customer["profile"]["id"], 20_000)
    quote = (
        await async_client.post(
            "/api/v1/checkout/quote",
            json={**cart((ghee, 2)), "use_wallet_paise": 20_000},
            headers=customer["headers"],
        )
    ).json()
    assert quote["subtotal_paise"] == 64_000
    assert quote["wallet_available_paise"] == 20_000
    assert quote["wallet_applied_paise"] == 20_000
    assert quote["payable_before_wallet_paise"] == 64_000
    assert quote["total_paise"] == 44_000

    order = await _place(async_client, customer, (ghee, 2), use_wallet_paise=20_000)
    assert order["wallet_paise"] == 20_000
    assert order["total_paise"] == 44_000
    assert order["payment_status"] == "pending"

    statement = await _wallet(async_client, customer)
    assert statement["balance_paise"] == 0
    entry = statement["entries"][0]
    assert entry["delta_paise"] == -20_000
    assert entry["reason"] == "order_payment"
    assert entry["balance_after_paise"] == 0
    assert entry["order_id"] == order["id"]
    # The ledger is the truth, not a parallel number.
    assert await ledger_sum(customer["profile"]["id"]) == 0


async def test_the_wallet_cannot_pay_more_than_the_order_costs(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    await give_wallet(customer["profile"]["id"], 5_00_000)

    order = await _place(async_client, customer, (ghee, 2), use_wallet_paise=5_00_000)
    assert order["wallet_paise"] == 64_000
    assert order["total_paise"] == 0
    # Nothing left to collect, so nothing is left pending.
    assert order["payment_status"] == "paid"

    statement = await _wallet(async_client, customer)
    assert statement["balance_paise"] == 5_00_000 - 64_000


async def test_a_wallet_is_private(
    async_client: AsyncClient,
    customer: dict[str, Any],
    make_token: Callable[..., str],
) -> None:
    await give_wallet(customer["profile"]["id"], 10_000)
    other = await new_customer(async_client, make_token, prefix="other")
    assert (await _wallet(async_client, other))["balance_paise"] == 0
    assert (await _wallet(async_client, customer))["balance_paise"] == 10_000


# --------------------------------------------------------------------------- #
# Referrals
# --------------------------------------------------------------------------- #
async def test_a_friend_gets_ten_percent_off_their_first_order(
    async_client: AsyncClient,
    customer: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    friend = await new_customer(async_client, make_token, prefix="friend")

    joined = await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=friend["headers"],
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["my_referral"]["status"] == "pending"

    quote = (
        await async_client.post(
            "/api/v1/checkout/quote", json=cart((ghee, 2)), headers=friend["headers"]
        )
    ).json()
    assert quote["subtotal_paise"] == 64_000
    assert quote["discount_paise"] == 6_400
    assert quote["discount_reason"] == "Referral 10% off"
    assert quote["total_paise"] == 57_600

    order = await _place(async_client, friend, (ghee, 2))
    assert order["discount_paise"] == 6_400
    assert order["discount_reason"] == "Referral 10% off"
    assert order["total_paise"] == 57_600

    # The second order pays full price: "first order only" is not a slogan.
    second = await _place(async_client, friend, (ghee, 2))
    assert second["discount_paise"] == 0
    assert second["total_paise"] == 64_000


async def test_the_referrer_is_paid_only_after_delivery(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    friend = await new_customer(async_client, make_token, prefix="friend")
    await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=friend["headers"],
    )
    order = await _place(async_client, friend, (ghee, 2))

    # Placed, not delivered: nothing owed yet.
    assert (await _wallet(async_client, customer))["balance_paise"] == 0
    program = (await _summary(async_client, customer))["referrals"]
    assert program["joined"] == 1
    assert program["credited"] == 0
    assert program["friends"][0]["status"] == "pending"

    await _deliver(async_client, admin, order)

    statement = await _wallet(async_client, customer)
    assert statement["balance_paise"] == 2_000
    entry = statement["entries"][0]
    assert entry["reason"] == "referral_bonus"
    assert entry["order_id"] == order["id"]

    program = (await _summary(async_client, customer))["referrals"]
    assert program["credited"] == 1
    assert program["earned_paise"] == 2_000

    bell = (await async_client.get("/api/v1/notifications", headers=customer["headers"])).json()
    assert any("added to your wallet" in item["title"] for item in bell["items"])


async def test_a_referral_is_refused_when_it_would_be_a_lie(
    async_client: AsyncClient,
    customer: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    # Self-referral.
    mine = await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=customer["headers"],
    )
    assert mine.status_code == 409
    assert mine.json()["error"]["code"] == "self_referral"

    # An unknown code.
    friend = await new_customer(async_client, make_token, prefix="friend")
    unknown = await async_client.post(
        "/api/v1/rewards/referral", json={"code": "ZZZZZZ"}, headers=friend["headers"]
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "referral_code_not_found"

    # Joining twice.
    other = await new_customer(async_client, make_token, prefix="other")
    first = await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=other["headers"],
    )
    assert first.status_code == 200
    again = await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=other["headers"],
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "referral_already_joined"

    # Joining after ordering: "first order" would no longer be true.
    late = await new_customer(async_client, make_token, prefix="late")
    await _place(async_client, late, (ghee, 2))
    refused = await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=late["headers"],
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "referral_after_first_order"


async def test_a_cancelled_first_order_pays_no_referral_bonus(
    async_client: AsyncClient,
    customer: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    friend = await new_customer(async_client, make_token, prefix="friend")
    await async_client.post(
        "/api/v1/rewards/referral",
        json={"code": customer["profile"]["referral_code"]},
        headers=friend["headers"],
    )
    order = await _place(async_client, friend, (ghee, 2))
    cancelled = await async_client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "changed my mind"},
        headers=friend["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text

    program = (await _summary(async_client, customer))["referrals"]
    assert program["friends"][0]["status"] == "void"
    assert program["credited"] == 0
    assert (await _wallet(async_client, customer))["balance_paise"] == 0


# --------------------------------------------------------------------------- #
# Scratch cards
# --------------------------------------------------------------------------- #
async def test_a_big_order_earns_a_locked_card(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    order = await _place(async_client, customer, (ghee, 7))  # ₹2,240 ≥ ₹2,000
    cards = (
        await async_client.get("/api/v1/rewards/scratch-cards", headers=customer["headers"])
    ).json()
    assert cards["locked"] == 1
    card = cards["cards"][0]
    assert card["status"] == "locked"
    assert card["order_id"] == order["id"]
    # The prize exists, but the client is not told it.
    assert card["amount_paise"] is None

    early = await async_client.post(
        f"/api/v1/rewards/scratch-cards/{card['id']}/reveal", headers=customer["headers"]
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "scratch_card_locked"


async def test_a_small_order_earns_no_card(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    await _place(async_client, customer, (ghee, 2))  # ₹640
    cards = (
        await async_client.get("/api/v1/rewards/scratch-cards", headers=customer["headers"])
    ).json()
    assert cards["cards"] == []


async def test_the_card_unlocks_on_delivery_and_pays_exactly_once(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _place(async_client, customer, (ghee, 7))
    await _deliver(async_client, admin, order)

    cards = (
        await async_client.get("/api/v1/rewards/scratch-cards", headers=customer["headers"])
    ).json()
    card = cards["cards"][0]
    assert card["status"] == "ready"
    assert card["expires_at"] is not None
    assert card["unlocked_at"] is not None

    revealed = await async_client.post(
        f"/api/v1/rewards/scratch-cards/{card['id']}/reveal", headers=customer["headers"]
    )
    assert revealed.status_code == 200, revealed.text
    body = revealed.json()
    assert 5_000 <= body["credited_paise"] <= 10_000
    assert body["card"]["amount_paise"] == body["credited_paise"]
    assert body["wallet_balance_paise"] == body["credited_paise"]

    again = await async_client.post(
        f"/api/v1/rewards/scratch-cards/{card['id']}/reveal", headers=customer["headers"]
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "scratch_card_used"

    statement = await _wallet(async_client, customer)
    assert statement["balance_paise"] == body["credited_paise"]
    assert len(statement["entries"]) == 1
    assert statement["entries"][0]["reason"] == "scratch_card"
    assert await ledger_sum(customer["profile"]["id"]) == body["credited_paise"]


async def test_a_card_belongs_to_one_customer(
    async_client: AsyncClient,
    customer: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    await _place(async_client, customer, (ghee, 7))
    card = (
        await async_client.get("/api/v1/rewards/scratch-cards", headers=customer["headers"])
    ).json()["cards"][0]

    nosy = await new_customer(async_client, make_token, prefix="nosy")
    stolen = await async_client.post(
        f"/api/v1/rewards/scratch-cards/{card['id']}/reveal", headers=nosy["headers"]
    )
    assert stolen.status_code == 404


# --------------------------------------------------------------------------- #
# Returns
# --------------------------------------------------------------------------- #
async def _delivered_order(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> dict[str, Any]:
    order = await _place(async_client, customer, (ghee, 2))
    await _deliver(async_client, admin, order)
    return (
        await async_client.get(f"/api/v1/orders/{order['id']}", headers=customer["headers"])
    ).json()


async def _request_return(
    async_client: AsyncClient, who: dict[str, Any], order: dict[str, Any], quantity: int = 1
) -> Any:
    line = order["items"][0]
    return await async_client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={
            "items": [{"order_item_id": line["id"], "quantity": quantity}],
            "reason": "The packet was torn",
        },
        headers=who["headers"],
    )


async def test_a_return_waits_for_approval_and_receipt_before_it_pays(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _delivered_order(async_client, customer, admin, ghee)
    stock_before = await stock_of(async_client, ghee["slug"])

    asked = await _request_return(async_client, customer, order)
    assert asked.status_code == 201, asked.text
    body = asked.json()
    assert body["status"] == "requested"
    assert body["refund_paise"] == order["items"][0]["unit_price_paise"]

    # The shop is told, and nothing is paid yet.
    shop_bell = (await async_client.get("/api/v1/notifications", headers=admin["headers"])).json()
    assert any("Return requested" in item["title"] for item in shop_bell["items"])
    assert (await _wallet(async_client, customer))["balance_paise"] == 0

    # Cannot receive before approving.
    early = await async_client.post(
        f"/api/v1/admin/returns/{body['id']}/received",
        json={"note": "back in the shop"},
        headers=admin["headers"],
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "return_not_approved"

    approved = await async_client.post(
        f"/api/v1/admin/returns/{body['id']}/decision",
        json={"approve": True, "note": "Bring it back"},
        headers=admin["headers"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    # Approved is still not paid.
    assert (await _wallet(async_client, customer))["balance_paise"] == 0

    received = await async_client.post(
        f"/api/v1/admin/returns/{body['id']}/received",
        json={"note": "Packet back on the shelf"},
        headers=admin["headers"],
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received_credited"

    statement = await _wallet(async_client, customer)
    assert statement["balance_paise"] == body["refund_paise"]
    assert statement["entries"][0]["reason"] == "return_refund"
    assert await stock_of(async_client, ghee["slug"]) == stock_before + 1

    # Marking received again is safe and pays nothing more (A-12).
    twice = await async_client.post(
        f"/api/v1/admin/returns/{body['id']}/received",
        json={"note": "double tap"},
        headers=admin["headers"],
    )
    assert twice.status_code == 200
    assert (await _wallet(async_client, customer))["balance_paise"] == body["refund_paise"]
    assert await ledger_sum(customer["profile"]["id"]) == body["refund_paise"]

    # The order is closed as returned, and the customer is told.
    closed = (
        await async_client.get(f"/api/v1/orders/{order['id']}", headers=customer["headers"])
    ).json()
    assert closed["status"] == "returned"
    bell = (await async_client.get("/api/v1/notifications", headers=customer["headers"])).json()
    assert any("Return received" in item["title"] for item in bell["items"])


async def test_a_return_needs_a_delivered_order(
    async_client: AsyncClient, customer: dict[str, Any], ghee: dict[str, Any]
) -> None:
    order = await _place(async_client, customer, (ghee, 2))
    refused = await _request_return(async_client, customer, order)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "return_order_not_delivered"


async def test_a_return_cannot_ask_for_more_than_was_ordered(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _delivered_order(async_client, customer, admin, ghee)
    too_many = await _request_return(async_client, customer, order, quantity=5)
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "return_quantity_too_high"

    twice = await _request_return(async_client, customer, order)
    assert twice.status_code == 201
    again = await _request_return(async_client, customer, order)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "return_already_open"


async def test_a_rejected_return_pays_nobody(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _delivered_order(async_client, customer, admin, ghee)
    asked = (await _request_return(async_client, customer, order)).json()

    rejected = await async_client.post(
        f"/api/v1/admin/returns/{asked['id']}/decision",
        json={"approve": False, "note": "The packet was opened"},
        headers=admin["headers"],
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    after = await async_client.post(
        f"/api/v1/admin/returns/{asked['id']}/received",
        json={"note": "should not pay"},
        headers=admin["headers"],
    )
    assert after.status_code == 409
    assert (await _wallet(async_client, customer))["balance_paise"] == 0


async def test_the_return_window_closes(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    order = await _delivered_order(async_client, customer, admin, ghee)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text(
                "update order_events set created_at = now() - interval '5 days' "
                "where order_id = :order_id and status = 'delivered'"
            ),
            {"order_id": order["id"]},
        )
        await session.commit()

    late = await _request_return(async_client, customer, order)
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "return_window_closed"


async def test_only_the_owner_can_decide_a_return(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    order = await _delivered_order(async_client, customer, admin, ghee)
    asked = (await _request_return(async_client, customer, order)).json()

    nosy = await new_customer(async_client, make_token, prefix="nosy")
    refused = await async_client.post(
        f"/api/v1/admin/returns/{asked['id']}/decision",
        json={"approve": True},
        headers=nosy["headers"],
    )
    assert refused.status_code == 403


# --------------------------------------------------------------------------- #
# Badges
# --------------------------------------------------------------------------- #
async def test_delivered_spend_earns_a_badge_and_a_message(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    # Gold at ₹500 keeps the test to one small order without touching the code.
    await set_settings(tier_gold_paise=50_000, tier_platinum_paise=2_00_000)
    before = await _summary(async_client, customer)
    assert before["tier"]["tier"] == "none"
    assert before["tier"]["next_tier_at_paise"] == 50_000

    order = await _place(async_client, customer, (ghee, 2))
    await _deliver(async_client, admin, order)

    after = await _summary(async_client, customer)
    assert after["tier"]["tier"] == "gold"
    assert after["tier"]["spend_paise"] == 64_000
    assert after["tier"]["next_tier"] == "platinum"
    # ₹14,000 into the ₹1,50,000 between gold and platinum.
    assert after["tier"]["progress_pct"] == 9
    assert after["tier"]["remaining_paise"] == 1_36_000

    bell = (await async_client.get("/api/v1/notifications", headers=customer["headers"])).json()
    assert any("Gold member" in item["title"] for item in bell["items"])


async def test_the_badge_progress_bar_moves(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    await set_settings(tier_gold_paise=50_000, tier_platinum_paise=1_00_000)
    first = await _place(async_client, customer, (ghee, 2))
    await _deliver(async_client, admin, first)

    progress = (await _summary(async_client, customer))["tier"]
    assert progress["tier"] == "gold"
    assert progress["next_tier"] == "platinum"
    assert progress["remaining_paise"] == 1_00_000 - 64_000
    assert 0 < progress["progress_pct"] < 100


async def test_a_return_takes_the_spend_back(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    ghee: dict[str, Any],
) -> None:
    await set_settings(tier_gold_paise=50_000, tier_platinum_paise=2_00_000)
    order = await _delivered_order(async_client, customer, admin, ghee)
    assert (await _summary(async_client, customer))["tier"]["tier"] == "gold"

    asked = (await _request_return(async_client, customer, order, quantity=2)).json()
    await async_client.post(
        f"/api/v1/admin/returns/{asked['id']}/decision",
        json={"approve": True},
        headers=admin["headers"],
    )
    await async_client.post(
        f"/api/v1/admin/returns/{asked['id']}/received",
        json={},
        headers=admin["headers"],
    )

    tier = (await _summary(async_client, customer))["tier"]
    assert tier["spend_paise"] == 0
    assert tier["tier"] == "none"


async def test_every_reward_route_needs_a_signed_in_customer(
    async_client: AsyncClient,
) -> None:
    for method, path in (
        ("get", "/api/v1/rewards"),
        ("get", "/api/v1/rewards/wallet"),
        ("get", "/api/v1/rewards/scratch-cards"),
        ("get", "/api/v1/returns"),
        ("post", "/api/v1/rewards/referral"),
    ):
        call = getattr(async_client, method)
        response = await (call(path, json={"code": "ABCDEF"}) if method == "post" else call(path))
        assert response.status_code == 401, (path, response.status_code)


async def test_an_order_id_that_is_not_yours_cannot_be_returned(
    async_client: AsyncClient,
    customer: dict[str, Any],
    admin: dict[str, Any],
    make_token: Callable[..., str],
    ghee: dict[str, Any],
) -> None:
    order = await _delivered_order(async_client, customer, admin, ghee)
    nosy = await new_customer(async_client, make_token, prefix="nosy")
    refused = await _request_return(async_client, nosy, order)
    assert refused.status_code == 404
    assert refused.json()["error"]["code"] == "order_not_found"
    assert uuid.UUID(order["id"])  # the order is real, just not theirs
