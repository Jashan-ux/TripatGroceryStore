"""Bulk add: a spreadsheet of products, validated row by row, committed all together.

The contract the shop asked for is "show me which rows are wrong, and do not add
half of it". So the importer runs in two phases:

1. **Validate everything** — parse the CSV, resolve each category slug and brand
   name, check the money, check the links. Nothing is written.
2. **Commit only if every row passed.** A file with one bad row adds nothing, and
   the response still tells the owner exactly which line to fix.

Prices in the file are **rupees**, because that is what a shopkeeper types. They
are converted with ``Decimal`` so ₹12.35 becomes 1235 paise, never 1234.999.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.models.catalogue import Profile
from app.repositories import admin_tools as repo
from app.schemas.admin_catalogue import (
    BulkResultOut,
    BulkRowOut,
    ProductCreateIn,
    VariantIn,
)
from app.services import admin_catalogue, uploads

REQUIRED_COLUMNS = ("name", "category", "price")
OPTIONAL_COLUMNS = (
    "mrp",
    "stock",
    "unit",
    "brand",
    "description",
    "image_url",
    "tags",
    "variant_label",
    "variant_price",
    "variant_stock",
)
MAX_ROWS = 500

HEADER_HINT = (
    "The first line must be a header. Required columns: name, category, price. "
    f"Optional: {', '.join(OPTIONAL_COLUMNS)}. Prices are in rupees."
)


@dataclass
class Row:
    line: int
    values: dict[str, str]
    errors: list[str] = field(default_factory=list)
    payload: ProductCreateIn | None = None


def _rupees_to_paise(value: str, *, field_name: str) -> int:
    """Exact conversion: ₹12.35 → 1235. Floats are never involved."""
    text = value.strip().replace(",", "").replace("₹", "")
    if not text:
        return 0
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError(
            f"{field_name} must be a number of rupees, for example 120 or 120.50.",
            code="bulk_bad_number",
            details={"field": field_name, "value": value[:40]},
        ) from exc
    if amount < 0:
        raise ValidationError(
            f"{field_name} cannot be negative.",
            code="bulk_bad_number",
            details={"field": field_name},
        )
    paise = amount * 100
    if paise != paise.to_integral_value():
        raise ValidationError(
            f"{field_name} cannot be finer than one paisa.",
            code="bulk_bad_number",
            details={"field": field_name, "value": value[:40]},
        )
    return int(paise)


def _parse_int(value: str, *, field_name: str) -> int:
    text = value.strip().replace(",", "")
    if not text:
        return 0
    try:
        number = int(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(
            f"{field_name} must be a whole number.",
            code="bulk_bad_number",
            details={"field": field_name, "value": value[:40]},
        ) from exc
    if number < 0:
        raise ValidationError(
            f"{field_name} cannot be negative.",
            code="bulk_bad_number",
            details={"field": field_name},
        )
    return number


def parse_csv(text: str) -> list[Row]:
    """Split the file into rows, checking only the header here."""
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        raise ValidationError("The file is empty.", code="bulk_empty_file")
    reader = csv.DictReader(io.StringIO(stripped))
    header = [column.strip().lower() for column in (reader.fieldnames or [])]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValidationError(
            f"The header is missing {', '.join(missing)}. {HEADER_HINT}",
            code="bulk_bad_header",
            details={"missing": missing},
        )
    rows: list[Row] = []
    for index, raw in enumerate(reader, start=2):
        values: dict[str, str] = {}
        for key, value in raw.items():
            if key is None:
                continue
            column = key.strip().lower()
            if isinstance(value, list):
                values[column] = ",".join(part for part in value if part)
            else:
                values[column] = (value or "").strip()
        if not any(values.values()):
            continue  # a blank line is not a row, not an error
        # A row with trailing extra columns shows up as key None — already skipped.
        if len(rows) >= MAX_ROWS:
            raise ValidationError(
                f"That file has more than {MAX_ROWS} products. Split it into smaller files.",
                code="bulk_too_many_rows",
                details={"max_rows": MAX_ROWS},
            )
        rows.append(Row(line=index, values=values))
    if not rows:
        raise ValidationError("The file has a header but no products.", code="bulk_empty_file")
    return rows


def _validate_row(
    row: Row,
    *,
    seen_names: dict[str, int],
    categories: dict[str, uuid.UUID],
    brands: dict[str, uuid.UUID],
) -> None:
    values = row.values
    name = values.get("name", "").strip()

    def fail(message: str) -> None:
        row.errors.append(message)

    if not name:
        fail("name is empty")
    elif len(name) > 200:
        fail("name is longer than 200 characters")
    else:
        key = name.lower()
        if key in seen_names:
            fail(f"name repeats line {seen_names[key]}")
        else:
            seen_names[key] = row.line

    category_slug = admin_catalogue.slugify(values.get("category", ""))
    category_id = categories.get(category_slug)
    if not values.get("category", "").strip():
        fail("category is empty")
    elif category_id is None:
        fail(f"category '{values['category'].strip()}' does not exist")

    price_paise = mrp_paise = stock = 0
    try:
        price_paise = _rupees_to_paise(values.get("price", ""), field_name="price")
        if price_paise <= 0:
            fail("price must be more than zero")
    except ValidationError as exc:
        fail(exc.message)
    try:
        mrp_paise = _rupees_to_paise(values.get("mrp", ""), field_name="mrp")
        if mrp_paise and price_paise and price_paise > mrp_paise:
            fail("price is higher than mrp")
    except ValidationError as exc:
        fail(exc.message)
    try:
        stock = _parse_int(values.get("stock", ""), field_name="stock")
    except ValidationError as exc:
        fail(exc.message)

    brand_name = values.get("brand", "").strip()
    brand_id = None
    if brand_name:
        brand_id = brands.get(brand_name.lower())
        if brand_id is None:
            fail(f"brand '{brand_name}' does not exist — add the brand first")

    image_url = values.get("image_url", "").strip()
    if image_url:
        try:
            uploads.safe_remote_image_url(image_url)
        except ValidationError as exc:
            fail(exc.message)

    variants: list[VariantIn] = []
    variant_label = values.get("variant_label", "").strip()
    if variant_label:
        try:
            variant_price = _rupees_to_paise(
                values.get("variant_price", ""), field_name="variant_price"
            )
            variant_stock = _parse_int(values.get("variant_stock", ""), field_name="variant_stock")
        except ValidationError as exc:
            fail(exc.message)
            variant_price = variant_stock = 0
        if variant_price <= 0:
            fail("variant_price must be more than zero when variant_label is used")
        variants.append(
            VariantIn(label=variant_label, price_paise=variant_price, stock=variant_stock)
        )

    tags = [entry.strip() for entry in values.get("tags", "").split("|") if entry.strip()]
    if category_id is None or row.errors:
        return
    try:
        row.payload = ProductCreateIn(
            name=name,
            category_id=category_id,
            brand_id=brand_id,
            description=values.get("description", "")[:4000],
            unit_label=values.get("unit", "")[:40],
            mrp_paise=mrp_paise,
            price_paise=price_paise,
            stock=stock,
            images=[image_url] if image_url else [],
            tags=tags[:20],
            variants=variants,
        )
    except Exception as exc:  # pydantic ValidationError carries the field detail
        fail(str(exc).splitlines()[0][:200])


async def run(
    session: AsyncSession,
    actor: Profile,
    *,
    csv_text: str,
    dry_run: bool,
) -> BulkResultOut:
    rows = parse_csv(csv_text)

    category_rows = await repo.list_categories_admin(session)
    categories = {category.slug: category.id for category in category_rows}
    brands = {brand.name.lower(): brand.id for brand in await repo.list_brands_admin(session)}

    seen: dict[str, int] = {}
    for row in rows:
        _validate_row(row, seen_names=seen, categories=categories, brands=brands)

    results = [
        BulkRowOut(
            line=row.line,
            status="error" if row.errors else "ok",
            name=row.values.get("name", ""),
            slug=admin_catalogue.slugify(row.values.get("name", "")) if not row.errors else "",
            category=row.values.get("category", ""),
            errors=row.errors,
        )
        for row in rows
    ]
    invalid = sum(1 for row in rows if row.errors)
    valid = len(rows) - invalid

    if invalid:
        return BulkResultOut(
            committed=False,
            total=len(rows),
            valid=valid,
            invalid=invalid,
            rows=results,
            message=(
                f"{invalid} row(s) need fixing. Nothing was added — the whole file must be "
                "valid before any of it is written."
            ),
        )
    if dry_run:
        return BulkResultOut(
            committed=False,
            total=len(rows),
            valid=valid,
            invalid=0,
            rows=results,
            message=f"All {valid} row(s) look good. Nothing was written (this was a check).",
        )

    created: list[Any] = []
    try:
        for row, result in zip(rows, results, strict=True):
            assert row.payload is not None  # validated above
            product = await admin_catalogue.create_product(session, actor, row.payload)
            result.product_id = product.id
            result.slug = product.slug
            created.append(product)
    except Exception:
        await session.rollback()
        raise

    return BulkResultOut(
        committed=True,
        total=len(rows),
        valid=valid,
        invalid=0,
        rows=results,
        created=len(created),
        message=f"Added {len(created)} product(s).",
    )


__all__ = ["HEADER_HINT", "Row", "parse_csv", "run"]
