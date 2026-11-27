"""The owner's catalogue tools, against a real database.

Covers the two promises that are easy to break and hard to notice: a product added
from the admin screen is *actually* on the storefront (A-07), and nothing the shop
deletes takes its order history with it (A-09).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text
from tests.support import place

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers, "profile": profile}


async def _category_id(async_client: AsyncClient, admin: dict[str, Any], slug: str) -> str:
    listing = await async_client.get("/api/v1/admin/catalogue/categories", headers=admin["headers"])
    assert listing.status_code == 200, listing.text
    for category in listing.json()["categories"]:
        if category["slug"] == slug:
            return str(category["id"])
    raise AssertionError(f"category {slug} missing from the admin listing")


async def _add_product(
    async_client: AsyncClient,
    admin: dict[str, Any],
    *,
    name: str,
    category_id: str,
    price_paise: int = 4500,
    stock: int = 10,
    **extra: Any,
) -> dict[str, Any]:
    response = await async_client.post(
        "/api/v1/admin/catalogue/products",
        json={
            "name": name,
            "category_id": category_id,
            "price_paise": price_paise,
            "mrp_paise": price_paise + 500,
            "unit_label": "1 kg",
            "stock": stock,
            **extra,
        },
        headers=admin["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #
async def test_the_catalogue_tools_are_owner_only(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    catalogue: dict[str, Any],
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    forbidden = [
        ("get", "/api/v1/admin/catalogue/products"),
        ("get", "/api/v1/admin/catalogue/categories"),
        ("get", "/api/v1/admin/catalogue/brands"),
        ("post", "/api/v1/admin/catalogue/products"),
        ("post", "/api/v1/admin/catalogue/products/bulk"),
        ("post", "/api/v1/admin/catalogue/categories"),
    ]
    for method, path in forbidden:
        call = getattr(async_client, method)
        kwargs: dict[str, Any] = {"headers": customer["headers"]}
        if method == "post":
            kwargs["json"] = {
                "name": "x",
                "category_id": category_id,
                "price_paise": 100,
                "csv": "",
            }
        response = await call(path, **kwargs)
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["error"]["code"] == "admin_only"


async def test_signed_out_callers_are_rejected(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/admin/catalogue/products")
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# A-07: the inline row reaches the storefront
# --------------------------------------------------------------------------- #
async def test_a_product_added_inline_appears_on_the_storefront(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    name = f"Fresh Coriander {uuid.uuid4().hex[:6]}"
    created = await _add_product(async_client, admin, name=name, category_id=category_id)

    # The product page itself…
    detail = await async_client.get(f"/api/v1/products/{created['slug']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == name
    assert detail.json()["price_paise"] == 4500

    # …and a search finds it, without any cache being cleared by hand.
    found = await async_client.get("/api/v1/products", params={"q": name.split()[-1]})
    assert found.status_code == 200
    assert any(item["name"] == name for item in found.json()["items"])

    # The category listing shows it too — that is the destination of the link
    # the admin row's "view" button opens.
    listing = await async_client.get(
        "/api/v1/products", params={"category": catalogue["child_slug"]}
    )
    assert listing.status_code == 200
    slugs = [item["slug"] for item in listing.json()["items"]]
    assert created["slug"] in slugs


async def test_two_products_may_share_a_name_but_never_a_url(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    name = f"Same Name {uuid.uuid4().hex[:6]}"
    first = await _add_product(async_client, admin, name=name, category_id=category_id)
    second = await _add_product(async_client, admin, name=name, category_id=category_id)

    assert first["slug"] != second["slug"]
    assert second["slug"].startswith(first["slug"])


async def test_the_inline_row_refuses_a_price_above_the_mrp(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    response = await async_client.post(
        "/api/v1/admin/catalogue/products",
        json={
            "name": "Overpriced",
            "category_id": category_id,
            "price_paise": 5000,
            "mrp_paise": 4000,
        },
        headers=admin["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mrp_below_price"


async def test_an_unknown_category_is_a_404(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await async_client.post(
        "/api/v1/admin/catalogue/products",
        json={"name": "Orphan", "category_id": str(uuid.uuid4()), "price_paise": 100},
        headers=admin["headers"],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "category_not_found"


# --------------------------------------------------------------------------- #
# A-09: editing
# --------------------------------------------------------------------------- #
async def test_editing_a_price_is_visible_to_the_storefront_and_audit_logged(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    product = await _add_product(async_client, admin, name="Editable Ghee", category_id=category_id)

    patched = await async_client.patch(
        f"/api/v1/admin/catalogue/products/{product['id']}",
        json={"price_paise": 4900, "stock": 3},
        headers=admin["headers"],
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["price_paise"] == 4900

    detail = (await async_client.get(f"/api/v1/products/{product['slug']}")).json()
    assert detail["price_paise"] == 4900
    assert detail["mrp_paise"] == 5000  # untouched by a partial update

    # A partial update is still checked against the *stored* MRP, not skipped
    # because the field was absent from the request.
    too_high = await async_client.patch(
        f"/api/v1/admin/catalogue/products/{product['id']}",
        json={"price_paise": 5400},
        headers=admin["headers"],
    )
    assert too_high.status_code == 422
    assert too_high.json()["error"]["code"] == "mrp_below_price"

    log = await async_client.get("/api/v1/admin/audit", headers=admin["headers"])
    assert log.status_code == 200, log.text
    entries = log.json()["items"]
    edited = next(row for row in entries if row["action"] == "product.updated")
    assert edited["entity"] == "product"
    assert edited["entity_id"] == product["id"]
    assert edited["before"]["price_paise"] == 4500
    assert edited["after"]["price_paise"] == 4900
    # The audit row names who did it, even years later.
    assert edited["actor_email"] == ADMIN_EMAIL


async def test_variants_are_replaced_wholesale(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    product = await _add_product(
        async_client,
        admin,
        name="Loose Spice",
        category_id=category_id,
        variants=[
            {"label": "100 g", "price_paise": 3000, "stock": 4},
            {"label": "250 g", "price_paise": 7000, "stock": 2},
        ],
    )
    assert [variant["label"] for variant in product["variants"]] == ["100 g", "250 g"]

    patched = await async_client.patch(
        f"/api/v1/admin/catalogue/products/{product['id']}",
        json={"variants": [{"label": "100 g", "price_paise": 3200, "stock": 9}]},
        headers=admin["headers"],
    )
    assert patched.status_code == 200, patched.text
    assert [variant["label"] for variant in patched.json()["variants"]] == ["100 g"]
    assert patched.json()["variants"][0]["stock"] == 9
    # Variant stock is what the storefront offers, not the product row.
    assert patched.json()["available_stock"] == 9


async def test_duplicate_variant_labels_are_refused(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    response = await async_client.post(
        "/api/v1/admin/catalogue/products",
        json={
            "name": "Twice Packed",
            "category_id": category_id,
            "price_paise": 1000,
            "variants": [
                {"label": "1 kg", "price_paise": 1000},
                {"label": "1 kg", "price_paise": 2000},
            ],
        },
        headers=admin["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "duplicate_variant_label"


# --------------------------------------------------------------------------- #
# A-09: deleting
# --------------------------------------------------------------------------- #
async def test_a_product_without_orders_is_really_deleted(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    product = await _add_product(async_client, admin, name="Disposable", category_id=category_id)

    deleted = await async_client.delete(
        f"/api/v1/admin/catalogue/products/{product['id']}", headers=admin["headers"]
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["outcome"] == "deleted"

    gone = await async_client.get(f"/api/v1/products/{product['slug']}")
    assert gone.status_code == 404


async def test_a_product_inside_an_order_is_hidden_instead_of_deleted(
    async_client: AsyncClient,
    admin: dict[str, Any],
    customer: dict[str, Any],
    catalogue: dict[str, Any],
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    product = await _add_product(
        async_client,
        admin,
        name="Ordered Once",
        category_id=category_id,
        stock=5,
        price_paise=60_000,  # the shop's minimum order is ₹500
    )
    placed = await place(
        async_client,
        customer,
        {"items": [{"product_id": product["id"], "variant_id": None, "quantity": 1}]},
    )
    assert placed.status_code == 201, placed.text
    order_id = placed.json()["id"]

    deleted = await async_client.delete(
        f"/api/v1/admin/catalogue/products/{product['id']}", headers=admin["headers"]
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["outcome"] == "deactivated"
    assert "past order line" in deleted.json()["message"]

    # The storefront can no longer buy it…
    hidden = await async_client.get(f"/api/v1/products/{product['slug']}")
    assert hidden.status_code == 404
    # …but the order still shows what was bought.
    order = await async_client.get(f"/api/v1/orders/{order_id}", headers=customer["headers"])
    assert order.status_code == 200
    assert order.json()["items"][0]["name"] == "Ordered Once"


async def test_deleting_a_category_that_still_holds_products_is_refused_then_reassigned(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    parent_id = await _category_id(async_client, admin, catalogue["parent_slug"])

    # A category of the test's own: reassigning really does move every product
    # out, so borrowing the shared fixture's category would take its products
    # with it.
    created = await async_client.post(
        "/api/v1/admin/catalogue/categories",
        json={"name": f"Temp Shelf {uuid.uuid4().hex[:6]}", "parent_id": parent_id},
        headers=admin["headers"],
    )
    assert created.status_code == 201, created.text
    temp_id = created.json()["id"]

    product = await _add_product(async_client, admin, name="Needs A Home", category_id=temp_id)

    refused = await async_client.delete(
        f"/api/v1/admin/catalogue/categories/{temp_id}", headers=admin["headers"]
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "category_not_empty"
    assert refused.json()["error"]["details"]["products"] >= 1

    moved = await async_client.delete(
        f"/api/v1/admin/catalogue/categories/{temp_id}",
        params={"reassign_to": parent_id},
        headers=admin["headers"],
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["outcome"] == "moved"
    assert moved.json()["products_moved"] == 1

    # The product survived and now lives in the parent…
    detail = await async_client.get(
        f"/api/v1/admin/catalogue/products/{product['id']}", headers=admin["headers"]
    )
    assert detail.status_code == 200
    assert detail.json()["category_id"] == parent_id

    # …and the category itself is gone in the same call, not left empty behind.
    absent = await async_client.get("/api/v1/admin/catalogue/categories", headers=admin["headers"])
    assert temp_id not in {category["id"] for category in absent.json()["categories"]}
    second_try = await async_client.delete(
        f"/api/v1/admin/catalogue/categories/{temp_id}", headers=admin["headers"]
    )
    assert second_try.status_code == 404

    # The product moved into the shared fixture's parent, which its teardown does
    # not sweep, so remove it the way the owner would.
    await async_client.delete(
        f"/api/v1/admin/catalogue/products/{product['id']}", headers=admin["headers"]
    )


async def test_categories_nest_only_one_level_deep(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    child_id = await _category_id(async_client, admin, catalogue["child_slug"])
    response = await async_client.post(
        "/api/v1/admin/catalogue/categories",
        json={"name": "Too Deep", "parent_id": child_id},
        headers=admin["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "category_too_deep"


async def test_a_category_cannot_be_its_own_parent(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    child_id = await _category_id(async_client, admin, catalogue["child_slug"])
    response = await async_client.patch(
        f"/api/v1/admin/catalogue/categories/{child_id}",
        json={"parent_id": child_id},
        headers=admin["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "category_self_parent"


# --------------------------------------------------------------------------- #
# Brands
# --------------------------------------------------------------------------- #
async def test_brands_are_created_once_and_deleted_only_when_unused(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    name = f"Test Brand {uuid.uuid4().hex[:6]}"
    created = await async_client.post(
        "/api/v1/admin/catalogue/brands",
        json={"name": name},
        headers=admin["headers"],
    )
    assert created.status_code == 201, created.text
    brand = created.json()

    duplicate = await async_client.post(
        "/api/v1/admin/catalogue/brands", json={"name": name}, headers=admin["headers"]
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "brand_exists"

    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    await _add_product(
        async_client,
        admin,
        name="Branded Atta",
        category_id=category_id,
        brand_id=brand["id"],
    )
    in_use = await async_client.delete(
        f"/api/v1/admin/catalogue/brands/{brand['id']}", headers=admin["headers"]
    )
    assert in_use.status_code == 409
    assert in_use.json()["error"]["code"] == "brand_in_use"

    listing = await async_client.get("/api/v1/admin/catalogue/brands", headers=admin["headers"])
    row = next(entry for entry in listing.json()["brands"] if entry["id"] == brand["id"])
    assert row["product_count"] == 1


async def test_an_unused_brand_can_be_deleted(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    created = await async_client.post(
        "/api/v1/admin/catalogue/brands",
        json={"name": f"Disposable Brand {uuid.uuid4().hex[:6]}"},
        headers=admin["headers"],
    )
    brand_id = created.json()["id"]
    deleted = await async_client.delete(
        f"/api/v1/admin/catalogue/brands/{brand_id}", headers=admin["headers"]
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["outcome"] == "deleted"


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
async def test_the_admin_listing_filters_and_pages(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    for index in range(3):
        await _add_product(
            async_client,
            admin,
            name=f"Paged Item {index}",
            category_id=category_id,
            stock=index,
        )

    page = await async_client.get(
        "/api/v1/admin/catalogue/products",
        params={"q": "Paged Item", "category_id": category_id, "page_size": 2},
        headers=admin["headers"],
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] >= 3
    assert len(body["items"]) == 2
    assert body["total_pages"] >= 2
    # The admin row shows what the storefront will offer.
    assert body["items"][0]["available_stock"] >= 0

    low = await async_client.get(
        "/api/v1/admin/catalogue/products",
        params={"q": "Paged Item", "low_stock": True},
        headers=admin["headers"],
    )
    assert low.status_code == 200
    assert all(item["stock"] <= item["low_stock_threshold"] for item in low.json()["items"])


async def test_the_audit_log_records_creation_and_deletion(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    category_id = await _category_id(async_client, admin, catalogue["child_slug"])
    product = await _add_product(async_client, admin, name="Audit Me", category_id=category_id)
    await async_client.delete(
        f"/api/v1/admin/catalogue/products/{product['id']}", headers=admin["headers"]
    )

    log = await async_client.get("/api/v1/admin/audit", headers=admin["headers"])
    actions = [row["action"] for row in log.json()["items"]]
    assert "product.created" in actions
    assert "product.deleted" in actions

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stored = await session.scalar(
            text("SELECT count(*) FROM audit_log WHERE entity = 'product'")
        )
    assert int(stored or 0) >= 2
