"""Database-backed API tests (catalogue, /me, admin gate, RLS).

These need a real Postgres and are skipped locally unless ``TEST_DATABASE_URL`` is
set; CI runs them against the service container after ``alembic upgrade head``.
Fixtures live in ``conftest.py`` so the order tests share them.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.core.config import Settings
from app.db.session import get_sessionmaker
from app.models.enums import UserRole
from httpx import AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.db


async def test_home_returns_categories_and_rails(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get("/api/v1/home")
    assert response.status_code == 200
    payload = response.json()
    slugs = [category["slug"] for category in payload["categories"]]
    assert catalogue["parent_slug"] in slugs
    rail_slugs = {rail["category"]["slug"] for rail in payload["rails"]}
    assert catalogue["parent_slug"] in rail_slugs


async def test_category_listing_is_scoped_to_the_category(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get(
        "/api/v1/products", params={"category": catalogue["parent_slug"], "page_size": 48}
    )
    assert response.status_code == 200
    payload = response.json()
    # Parent category includes its children's products.
    assert payload["total"] >= 3
    assert {item["slug"] for item in payload["items"]} >= {
        catalogue["ghee_slug"],
        catalogue["oil_slug"],
    }
    # Nothing outside this category leaks in.
    assert all(item["category_slug"] == catalogue["child_slug"] for item in payload["items"])


async def test_search_matches_partial_words(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get("/api/v1/products", params={"q": "mustard"})
    assert response.status_code == 200
    slugs = [item["slug"] for item in response.json()["items"]]
    assert catalogue["oil_slug"] in slugs


async def test_search_is_case_insensitive(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    upper = await async_client.get("/api/v1/products", params={"q": "GHEE"})
    lower = await async_client.get("/api/v1/products", params={"q": "ghee"})
    assert upper.status_code == lower.status_code == 200
    assert upper.json()["total"] == lower.json()["total"] >= 1


async def test_in_stock_filter_excludes_zero_stock(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get(
        "/api/v1/products",
        params={"category": catalogue["parent_slug"], "in_stock": "true", "page_size": 48},
    )
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()["items"]}
    assert catalogue["ghee_slug"] in slugs
    assert catalogue["oil_slug"] not in slugs


async def test_price_filter_and_sorting(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get(
        "/api/v1/products",
        params={
            "category": catalogue["parent_slug"],
            "min_price_paise": 20_000,
            "sort": "price_desc",
            "page_size": 48,
        },
    )
    assert response.status_code == 200
    prices = [item["price_paise"] for item in response.json()["items"]]
    assert prices == sorted(prices, reverse=True)
    assert all(price >= 20_000 for price in prices)


async def test_pagination_metadata(async_client: AsyncClient, catalogue: dict[str, Any]) -> None:
    response = await async_client.get(
        "/api/v1/products",
        params={"category": catalogue["parent_slug"], "page": 1, "page_size": 2},
    )
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) <= 2
    assert payload["total_pages"] == -(-payload["total"] // 2)


async def test_product_detail_includes_variants(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get(f"/api/v1/products/{catalogue['loose_slug']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_variants"] is True
    assert [variant["label"] for variant in payload["variants"]] == ["100 g", "250 g"]
    # Stock is the sum of active variants, not the parent column.
    assert payload["stock"] == 5
    assert payload["in_stock"] is True


async def test_unknown_product_returns_structured_404(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> None:
    response = await async_client.get("/api/v1/products/does-not-exist-at-all")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "product_not_found"
    assert body["error"]["request_id"]


# --------------------------------------------------------------------------- #
# Auth and authorisation (S‑01 … S‑03, A‑01, C‑06)
# --------------------------------------------------------------------------- #
async def test_me_requires_a_token(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


@pytest.mark.usefixtures("use_local_keys")
async def test_first_login_creates_a_profile(
    async_client: AsyncClient, make_token: Callable[..., str], catalogue: dict[str, Any]
) -> None:
    email = f"test-new-{uuid.uuid4().hex[:6]}@example.com"
    token = make_token(email)
    response = await async_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    profile = response.json()
    assert profile["email"] == email
    assert profile["role"] == "customer"  # role comes from the database, not the token
    assert profile["has_phone"] is False
    assert len(profile["referral_code"]) == 6
    assert profile["loyalty_tier"] == "none"

    # A second call returns the same profile instead of creating another.
    again = await async_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert again.json()["id"] == profile["id"]


@pytest.mark.usefixtures("use_local_keys")
async def test_phone_is_normalised_and_unique(
    async_client: AsyncClient, make_token: Callable[..., str], catalogue: dict[str, Any]
) -> None:
    first_email = f"test-phone-a-{uuid.uuid4().hex[:6]}@example.com"
    second_email = f"test-phone-b-{uuid.uuid4().hex[:6]}@example.com"
    first = await async_client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {make_token(first_email)}"}
    )
    second = await async_client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {make_token(second_email)}"}
    )
    assert first.status_code == second.status_code == 200

    saved = await async_client.post(
        "/api/v1/me/phone",
        json={"phone": "+91 98765-43210"},
        headers={"Authorization": f"Bearer {make_token(first_email)}"},
    )
    assert saved.status_code == 200
    assert saved.json()["phone"] == "9876543210"
    assert saved.json()["has_phone"] is True

    duplicate = await async_client.post(
        "/api/v1/me/phone",
        json={"phone": "9876543210"},
        headers={"Authorization": f"Bearer {make_token(second_email)}"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "phone_already_used"

    invalid = await async_client.post(
        "/api/v1/me/phone",
        json={"phone": "12345"},
        headers={"Authorization": f"Bearer {make_token(second_email)}"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_phone"


@pytest.mark.usefixtures("use_local_keys")
async def test_admin_routes_reject_customers(
    async_client: AsyncClient, make_token: Callable[..., str], catalogue: dict[str, Any]
) -> None:
    token = make_token(f"test-customer-{uuid.uuid4().hex[:6]}@example.com")
    response = await async_client.get(
        "/api/v1/admin/whoami", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_only"


@pytest.mark.usefixtures("use_local_keys")
async def test_admin_routes_allow_the_owner(
    async_client: AsyncClient, make_token: Callable[..., str], catalogue: dict[str, Any]
) -> None:
    # `owner@example.com` is in ADMIN_EMAILS for this test's settings.
    token = make_token("owner@example.com")
    response = await async_client.get(
        "/api/v1/admin/whoami", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.usefixtures("use_local_keys")
async def test_demoting_the_profile_revokes_admin_immediately(
    async_client: AsyncClient,
    make_token: Callable[..., str],
    catalogue: dict[str, Any],
    auth_settings: Settings,
) -> None:
    """A‑01: the role is read per request, so a demotion takes effect at once."""
    token = make_token("owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await async_client.get("/api/v1/admin/whoami", headers=headers)
    assert created.status_code == 200

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("UPDATE profiles SET role = :role WHERE id = :id"),
            {"role": UserRole.customer.value, "id": created.json()["id"]},
        )
        await session.commit()

    after = await async_client.get("/api/v1/admin/whoami", headers=headers)
    assert after.status_code == 403


async def test_public_tables_have_no_anon_access(catalogue: dict[str, Any]) -> None:
    """S‑01: even with the anon key, PostgREST callers get nothing.

    RLS is asserted on every public table first — that holds on any Postgres.
    The `anon` role only exists where PostgREST runs, so that probe is skipped
    elsewhere rather than being asserted against a role that is not there.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        unguarded = (
            await session.scalars(
                text(
                    """
                    SELECT c.relname
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind = 'r'
                      AND NOT c.relrowsecurity
                    ORDER BY c.relname
                    """
                )
            )
        ).all()
        assert unguarded == [], f"row level security is off on {unguarded}"

        has_anon = bool(
            await session.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')")
            )
        )

    if not has_anon:
        pytest.skip("no PostgREST `anon` role in this database; the RLS check above stands")

    # Run as the `anon` role inside a rolled-back transaction so the assertion is
    # about privileges, not about the connection's own role.
    async with sessionmaker() as session:
        transaction = await session.begin()
        try:
            await session.execute(text("SET LOCAL ROLE anon"))
            with pytest.raises(Exception) as excinfo:
                await session.execute(text("SELECT count(*) FROM public.products"))
            assert "permission denied" in str(excinfo.value).lower()
        finally:
            await transaction.rollback()

    # And through the API's own role the data is readable, proving the test above
    # failed for the right reason.
    async with sessionmaker() as session:
        assert await session.scalar(text("SELECT count(*) FROM public.products")) is not None
