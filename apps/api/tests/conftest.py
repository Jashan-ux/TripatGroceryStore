"""Test fixtures.

Unit/API tests run with no external services. Anything that needs a real
Postgres is marked ``@pytest.mark.db`` and pointed at ``TEST_DATABASE_URL``;
when that variable is unset the test is skipped with a reason, never silently
"passed" (see docs/TESTING.md).
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import jwt
import pytest
from app.core.config import Settings
from app.db.session import get_sessionmaker
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from tests.support import new_customer, product_detail

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.main import create_app

    return create_app()


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set — database tests run in CI only")
    return url


SUPABASE_URL = "https://project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"

# Emails the suite creates; cleaned up so the database can be reused as-is.
_TEST_EMAIL_PATTERNS = (
    "test-%@example.com",
    "buyer-%@example.com",
    "other-%@example.com",
    "nophone-%@example.com",
    "race-%@example.com",
)


@pytest.fixture()
async def catalogue() -> AsyncIterator[dict[str, Any]]:
    """A tiny, fully-linked catalogue: one brand, two categories, three products."""
    sessionmaker = get_sessionmaker()
    suffix = uuid.uuid4().hex[:8]
    slugs: dict[str, Any] = {}

    async with sessionmaker() as session:
        brand_id = await session.scalar(
            text("INSERT INTO brands (slug, name) VALUES (:slug, :name) RETURNING id"),
            {"slug": f"test-brand-{suffix}", "name": f"Test Brand {suffix}"},
        )
        parent_id = await session.scalar(
            text(
                "INSERT INTO categories (slug, name, emoji, sort_order) "
                "VALUES (:slug, :name, '🧪', 99) RETURNING id"
            ),
            {"slug": f"test-parent-{suffix}", "name": f"Test Parent {suffix}"},
        )
        child_id = await session.scalar(
            text(
                "INSERT INTO categories (slug, name, sort_order, parent_id) "
                "VALUES (:slug, :name, 1, :parent) RETURNING id"
            ),
            {"slug": f"test-child-{suffix}", "name": f"Test Child {suffix}", "parent": parent_id},
        )
        product_ids = []
        for index, (name, price, stock) in enumerate(
            [("Test Ghee 1L", 32_000, 12), ("Test Mustard Oil 1L", 18_000, 0)]
        ):
            product_id = await session.scalar(
                text(
                    "INSERT INTO products (slug, name, description, brand_id, category_id, "
                    "mrp_paise, price_paise, unit_label, stock, tags, rating) VALUES "
                    "(:slug, :name, :description, :brand, :category, :mrp, :price, '1 L', :stock, "
                    "ARRAY['bestseller'], 4.5) RETURNING id"
                ),
                {
                    "slug": f"test-product-{suffix}-{index}",
                    "name": name,
                    "description": "A product used by the test suite.",
                    "brand": brand_id,
                    "category": child_id,
                    "mrp": price + 1_500,
                    "price": price,
                    "stock": stock,
                },
            )
            product_ids.append(product_id)

        variant_product_id = await session.scalar(
            text(
                "INSERT INTO products (slug, name, description, category_id, mrp_paise, "
                "price_paise, unit_label, stock) VALUES "
                "(:slug, :name, '', :category, 13000, 11500, 'per pack', 0) RETURNING id"
            ),
            {
                "slug": f"test-loose-{suffix}",
                "name": "Test Loose Powder",
                "category": child_id,
            },
        )
        for order, (label, mrp, price, stock) in enumerate(
            [("100 g", 13_000, 11_500, 5), ("250 g", 30_000, 26_500, 0)]
        ):
            await session.execute(
                text(
                    "INSERT INTO product_variants (product_id, label, mrp_paise, price_paise, "
                    "stock, sort_order) VALUES (:product, :label, :mrp, :price, :stock, :order)"
                ),
                {
                    "product": variant_product_id,
                    "label": label,
                    "mrp": mrp,
                    "price": price,
                    "stock": stock,
                    "order": order,
                },
            )

        await session.commit()

    slugs = {
        "suffix": suffix,
        "brand_id": brand_id,
        "parent_slug": f"test-parent-{suffix}",
        "child_slug": f"test-child-{suffix}",
        "ghee_slug": f"test-product-{suffix}-0",
        "oil_slug": f"test-product-{suffix}-1",
        "loose_slug": f"test-loose-{suffix}",
    }

    yield slugs

    async with sessionmaker() as session:
        # Orders reference products with RESTRICT, so they go before the catalogue.
        await session.execute(text("DELETE FROM orders"))
        await session.execute(text("DELETE FROM addresses"))
        await session.execute(
            text("DELETE FROM product_variants WHERE product_id = :id"), {"id": variant_product_id}
        )
        await session.execute(
            text("DELETE FROM products WHERE category_id = :id"), {"id": child_id}
        )
        await session.execute(text("DELETE FROM categories WHERE id = :id"), {"id": child_id})
        await session.execute(text("DELETE FROM categories WHERE id = :id"), {"id": parent_id})
        await session.execute(text("DELETE FROM brands WHERE id = :id"), {"id": brand_id})
        await session.execute(
            text("DELETE FROM profiles WHERE email LIKE :pattern"),
            {"pattern": "test-%@example.com"},
        )
        await session.commit()


async def _wipe_profiles() -> None:
    """Remove rows the tests created, so every test starts from the same place.

    Order matters: order lines and events cascade from `orders`, notifications
    cascade from `profiles`, and `email_messages` has no owner at all — it is an
    outbox, so it is emptied explicitly. (Leaving it behind makes the outbox
    assertions order-dependent: a queued row from an earlier test is still
    `queued` for the next one.)
    """
    from app.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(text("DELETE FROM email_messages"))
        await session.execute(text("DELETE FROM notifications"))
        await session.execute(text("DELETE FROM orders"))
        await session.execute(text("DELETE FROM addresses"))
        await session.execute(text("DELETE FROM profiles"))
        await session.commit()


@pytest.fixture()
async def db_environment(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    """Point the API at the throwaway test database, for `db`-marked tests only.

    ``DATABASE_URL`` on a developer machine points at the hosted project, so these
    tests must never inherit it: the engine is rebuilt against ``TEST_DATABASE_URL``
    (set by CI) and torn down afterwards, leaving no rows behind.
    """
    if request.node.get_closest_marker("db") is None:
        yield
        return

    database_url = request.getfixturevalue("database_url")
    from app.core.config import get_settings
    from app.db.session import dispose_engine

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATABASE_DIRECT_URL", database_url)
    get_settings.cache_clear()
    await dispose_engine()
    try:
        yield
    finally:
        try:
            await _wipe_profiles()
        except Exception:  # pragma: no cover - database already gone
            logging.getLogger(__name__).debug("profile cleanup skipped")
        await dispose_engine()
        monkeypatch.undo()
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def _db_environment(db_environment: None) -> AsyncIterator[None]:
    """Autouse wrapper: db-marked tests get the test database, others are untouched."""
    yield


@pytest.fixture(scope="module")
def signing_key() -> tuple[Any, Any]:
    private = ec.generate_private_key(ec.SECP256R1())
    return private, private.public_key()


@pytest.fixture()
def auth_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Point token verification at a local key instead of the project's JWKS."""
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_URL=SUPABASE_URL,
        SUPABASE_JWT_SECRET="",
        ADMIN_EMAILS="owner@example.com",
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    # `bootstrap_role` lives in the service layer and calls get_settings itself.
    monkeypatch.setattr("app.services.profiles.get_settings", lambda: settings)
    return settings


@pytest.fixture()
def use_local_keys(
    signing_key: tuple[Any, Any], auth_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, public = signing_key

    class Provider:
        def get_signing_key(self, token: str) -> Any:
            return type("SigningKey", (), {"key": public})()

    monkeypatch.setattr(
        "app.core.security.get_signing_key_provider", lambda settings=None: Provider()
    )


@pytest.fixture()
def make_token(signing_key: tuple[Any, Any]) -> Callable[..., str]:
    private, _ = signing_key

    def _make(email: str, *, subject: uuid.UUID | None = None, expires_in: int = 600) -> str:
        now = int(time.time())
        # Deterministic per address: requesting the same user twice in a test
        # must not look like two sign-ups racing on the same email.
        user_id = subject or uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{email}")
        return jwt.encode(
            {
                "sub": str(user_id),
                "email": email,
                "email_verified": True,
                "aud": "authenticated",
                "iss": ISSUER,
                "iat": now,
                "exp": now + expires_in,
                "app_metadata": {"provider": "email"},
                "user_metadata": {"full_name": "Test Customer"},
            },
            private,
            algorithm="ES256",
            headers={"kid": "test"},
        )

    return _make


# --------------------------------------------------------------------------- #
# Order fixtures, shared by the customer and admin suites
# --------------------------------------------------------------------------- #
@pytest.fixture()
async def customer(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    """A signed-in customer with a phone number and one saved address."""
    return await new_customer(async_client, make_token)


@pytest.fixture()
async def products(async_client: AsyncClient, catalogue: dict[str, Any]) -> dict[str, Any]:
    """The catalogue fixture's products as the API returns them."""
    ghee = await product_detail(async_client, catalogue["ghee_slug"])
    loose = await product_detail(async_client, catalogue["loose_slug"])
    return {"ghee": ghee, "loose": loose}


@pytest.fixture()
async def big_ticket(
    async_client: AsyncClient, catalogue: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """A ₹600 product with 3 units: above the ₹500 minimum, so quantity 1 works."""
    sessionmaker = get_sessionmaker()
    slug = f"test-big-{uuid.uuid4().hex[:8]}"
    async with sessionmaker() as session:
        category_id = await session.scalar(
            text("SELECT id FROM categories WHERE slug = :slug"), {"slug": catalogue["child_slug"]}
        )
        product_id = await session.scalar(
            text(
                "INSERT INTO products (slug, name, description, category_id, mrp_paise, "
                "price_paise, unit_label, stock) VALUES (:slug, 'Test Atta 10 kg', '', "
                ":category, 70000, 60000, '10 kg', 3) RETURNING id"
            ),
            {"slug": slug, "category": category_id},
        )
        await session.commit()

    yield await product_detail(async_client, slug)

    async with sessionmaker() as session:
        await session.execute(text("DELETE FROM orders"))
        await session.execute(
            text("DELETE FROM order_items WHERE product_id = :id"), {"id": product_id}
        )
        await session.execute(text("DELETE FROM products WHERE id = :id"), {"id": product_id})
        await session.commit()
