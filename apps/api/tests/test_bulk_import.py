"""Bulk add: one bad row in a hundred means nothing is written (A-08).

The promise the owner cares about is "either the whole sheet lands or none of it
does, and I get told which line is wrong". These tests hold the API to exactly
that, including the rupee-to-paise conversion, because a rounded price is a real
price the shop charges.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from app.db.session import get_sessionmaker
from httpx import AsyncClient
from sqlalchemy import text

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers}


async def _child_slug(async_client: AsyncClient, admin: dict[str, Any], slug: str) -> str:
    listing = await async_client.get("/api/v1/admin/catalogue/categories", headers=admin["headers"])
    assert listing.status_code == 200, listing.text
    assert any(category["slug"] == slug for category in listing.json()["categories"])
    return slug


def _csv(*rows: str, header: str = "name,category,price,unit,mrp,stock") -> str:
    return "\n".join([header, *rows])


async def _bulk(
    async_client: AsyncClient,
    admin: dict[str, Any],
    csv: str,
    *,
    dry_run: bool = False,
) -> Any:
    return await async_client.post(
        "/api/v1/admin/catalogue/products/bulk",
        json={"csv": csv, "dry_run": dry_run},
        headers=admin["headers"],
    )


async def _product_count() -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return int(await session.scalar(text("SELECT count(*) FROM products")) or 0)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
async def test_a_clean_sheet_commits_every_row(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    tag = uuid.uuid4().hex[:6]
    csv = _csv(
        f"Bulk Atta {tag},{slug},99.50,5 kg",
        f"Bulk Rice {tag},{slug},120,5 kg,150,8",
    )
    before = await _product_count()

    response = await _bulk(async_client, admin, csv)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["committed"] is True
    assert body["created"] == 2
    assert body["invalid"] == 0
    assert {row["status"] for row in body["rows"]} == {"ok"}

    assert await _product_count() == before + 2
    # Rupees became exact paise: ₹99.50 is 9950, not 9950.0000001 or 9900.
    detail = (await async_client.get(f"/api/v1/products/bulk-atta-{tag}")).json()
    assert detail["price_paise"] == 9950
    priced = (await async_client.get(f"/api/v1/products/bulk-rice-{tag}")).json()
    assert priced["price_paise"] == 12000
    assert priced["mrp_paise"] == 15000
    assert priced["stock"] == 8


async def test_a_dry_run_reports_without_writing(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    tag = uuid.uuid4().hex[:6]
    before = await _product_count()

    response = await _bulk(async_client, admin, _csv(f"Dry Run {tag},{slug},10"), dry_run=True)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["committed"] is False
    assert body["created"] == 0
    assert body["rows"][0]["status"] == "ok"
    assert body["valid"] == 1
    assert await _product_count() == before, "a dry run must not touch the catalogue"

    # And nothing was left behind for the storefront either.
    missing = await async_client.get(f"/api/v1/products/dry-run-{tag}")
    assert missing.status_code == 404


# --------------------------------------------------------------------------- #
# All-or-nothing
# --------------------------------------------------------------------------- #
async def test_one_bad_row_rolls_back_the_whole_sheet(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    tag = uuid.uuid4().hex[:6]
    before = await _product_count()

    response = await _bulk(
        async_client,
        admin,
        _csv(
            f"Good Row {tag},{slug},50",  # line 2 — fine
            f"Bad Row {tag},no-such-category,50",  # line 3 — unknown category
            f"Pricier Than MRP {tag},{slug},100,,80",  # line 4 — price above MRP
            f"Free Row {tag},{slug},-5",  # line 5 — negative price
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["committed"] is False
    assert body["created"] == 0
    assert body["invalid"] == 3
    assert body["valid"] == 1

    assert await _product_count() == before, "one bad row must not add the good ones"
    assert (await async_client.get(f"/api/v1/products/good-row-{tag}")).status_code == 404

    errors = {row["line"]: row for row in body["rows"] if row["status"] == "error"}
    assert set(errors) == {3, 4, 5}
    assert "category" in errors[3]["errors"][0].lower()
    assert "mrp" in errors[4]["errors"][0].lower()
    assert "price" in errors[5]["errors"][0].lower()
    # Every row is echoed back with its number, so the owner can fix the sheet
    # without guessing which line the message is about.
    assert [row["line"] for row in body["rows"]] == [2, 3, 4, 5]


async def test_a_name_repeated_inside_the_sheet_is_caught(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    tag = uuid.uuid4().hex[:6]
    response = await _bulk(
        async_client,
        admin,
        _csv(f"Twin {tag},{slug},10", f"twin {tag},{slug},12"),
    )
    body = response.json()
    assert body["committed"] is False
    assert body["invalid"] == 1
    assert body["rows"][1]["line"] == 3


async def test_an_image_url_pointing_inside_the_network_is_refused(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    tag = uuid.uuid4().hex[:6]
    header = "name,category,price,image_url"
    response = await _bulk(
        async_client,
        admin,
        "\n".join(
            [
                header,
                f"Plain {tag},{slug},10,https://images.example.com/plain.jpg",
                f"Sneaky {tag},{slug},10,http://169.254.169.254/latest/meta-data/",
                f"Local {tag},{slug},10,https://localhost/admin.jpg",
            ]
        ),
    )
    body = response.json()
    assert body["committed"] is False
    assert body["invalid"] == 2
    assert "image" in body["rows"][1]["errors"][0].lower()


# --------------------------------------------------------------------------- #
# Bad files
# --------------------------------------------------------------------------- #
async def test_the_sheet_must_have_the_columns_we_need(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await _bulk(async_client, admin, _csv("Only A Name,", header="name,note"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "bulk_bad_header"
    assert "category" in error["message"]


async def test_an_empty_sheet_is_refused(async_client: AsyncClient, admin: dict[str, Any]) -> None:
    response = await _bulk(async_client, admin, "name,category,price\n\n")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "bulk_empty_file"


async def test_a_sheet_over_the_row_cap_is_refused(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    rows = [f"Over Cap {uuid.uuid4().hex[:4]},{slug},10" for _ in range(501)]
    response = await _bulk(async_client, admin, _csv(*rows))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "bulk_too_many_rows"


async def test_an_excel_export_with_a_byte_order_mark_still_parses(
    async_client: AsyncClient, admin: dict[str, Any], catalogue: dict[str, Any]
) -> None:
    slug = await _child_slug(async_client, admin, catalogue["child_slug"])
    tag = uuid.uuid4().hex[:6]
    csv = "\ufeff" + _csv(f"BOM Row {tag},{slug},10")
    response = await _bulk(async_client, admin, csv)
    assert response.status_code == 200, response.text
    assert response.json()["committed"] is True


async def test_bulk_import_is_owner_only(
    async_client: AsyncClient, customer: dict[str, Any]
) -> None:
    response = await async_client.post(
        "/api/v1/admin/catalogue/products/bulk",
        json={"csv": "name,category,price\nx,y,1", "dry_run": True},
        headers=customer["headers"],
    )
    assert response.status_code == 403
