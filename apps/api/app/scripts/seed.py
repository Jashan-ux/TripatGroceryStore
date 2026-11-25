"""Seed the catalogue (and optionally staging users).

Usage::

    python -m app.scripts.seed                 # apply catalogue + settings
    python -m app.scripts.seed --print-sql     # print SQL instead of executing
    python -m app.scripts.seed --with-users    # also create staging auth users

Safety: refuses to run when ``ENVIRONMENT=production``. Idempotent — every insert
is keyed on a natural slug, so re-running updates prices instead of duplicating
rows. The generated SQL is what actually runs, which keeps a single source of
truth for local, staging and the hosted project.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.scripts import seed_data as data
from app.scripts.seed_data import ProductSeed

logger = get_logger("seed")


def paise(rupees: float | int) -> int:
    """Rupees → integer paise, without float drift (₹1.15 → 115)."""
    return int((Decimal(str(rupees)) * 100).to_integral_value())


def brand_ref(slug: str | None) -> str:
    """Unbranded (loose) items store a NULL brand instead of a fake one."""
    if slug is None:
        return "NULL"
    return f"(SELECT id FROM public.brands WHERE slug={_quote(slug)})"


def display_prices(product: ProductSeed) -> tuple[float, float]:
    """Card prices: the cheapest variant's price *and* that same variant's MRP.

    Taking max(MRP) against min(price) would advertise a discount nobody offers.
    """
    if not product.variants:
        return product.mrp, product.price
    cheapest = min(product.variants, key=lambda variant: variant.price)
    return cheapest.mrp, cheapest.price


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _text_array(values: tuple[str, ...] | list[str]) -> str:
    if not values:
        return "'{}'::text[]"
    inner = ", ".join(f'"{value}"' for value in values)
    return _quote("{" + inner + "}") + "::text[]"


def build_compact_sql(
    *, products: tuple[data.ProductSeed, ...] | None = None, include_reference: bool = True
) -> str:
    """Multi-row form of the same seed, used when applying it through an HTTP client.

    Identical semantics to :func:`build_sql` — one INSERT per table with several
    VALUES rows — but far fewer round trips. ``products`` lets a caller apply the
    catalogue in chunks.
    """
    rows: list[str] = []
    if include_reference:
        category_rows: list[str] = []
        for category in data.CATEGORIES:
            category_rows.append(
                "("
                + ", ".join(
                    [
                        _quote(category.slug),
                        _quote(category.name),
                        _quote(category.emoji),
                        str(category.sort_order),
                        _quote(category.description),
                        "NULL",
                        "true",
                    ]
                )
                + ")"
            )
        for category in data.CATEGORIES:
            for child_slug, child_name, child_order in category.children:
                category_rows.append(
                    "("
                    + ", ".join(
                        [
                            _quote(child_slug),
                            _quote(child_name),
                            "NULL",
                            str(child_order),
                            _quote(child_name + " at MSG Store"),
                            f"(SELECT id FROM public.categories WHERE slug={_quote(category.slug)})",
                            "true",
                        ]
                    )
                    + ")"
                )
        rows.append(
            "INSERT INTO public.categories "
            "(slug, name, emoji, sort_order, description, parent_id, is_active) VALUES\n"
            + ",\n".join(category_rows)
            + "\nON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, emoji = EXCLUDED.emoji, "
            "sort_order = EXCLUDED.sort_order, description = EXCLUDED.description, "
            "parent_id = EXCLUDED.parent_id, is_active = true;"
        )
        brand_rows = [f"({_quote(b.slug)}, {_quote(b.name)}, true)" for b in data.BRANDS]
        rows.append(
            "INSERT INTO public.brands (slug, name, is_active) VALUES\n"
            + ",\n".join(brand_rows)
            + "\nON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, is_active = true;"
        )

    product_rows: list[str] = []
    variant_rows: list[str] = []
    for product in products if products is not None else data.PRODUCTS:
        variants = list(product.variants)
        parent_stock = 0 if variants else product.stock
        mrp, price = display_prices(product)
        description = product.description or f"{product.name} from Tripat Pansari · MSG Store."
        product_rows.append(
            "("
            + ", ".join(
                [
                    _quote(product.slug),
                    _quote(" ".join(product.name.split())),
                    _quote(description),
                    brand_ref(product.brand),
                    f"(SELECT id FROM public.categories WHERE slug={_quote(product.category)})",
                    str(paise(mrp)),
                    str(paise(price)),
                    _quote(product.unit),
                    str(parent_stock),
                    "10",
                    "'{}'::text[]",
                    _text_array(list(product.tags)),
                    str(product.rating),
                    "true",
                ]
            )
            + ")"
        )
        for index, variant in enumerate(variants):
            variant_rows.append(
                "("
                + ", ".join(
                    [
                        f"(SELECT id FROM public.products WHERE slug={_quote(product.slug)})",
                        _quote(variant.label),
                        str(paise(variant.mrp)),
                        str(paise(variant.price)),
                        str(variant.stock),
                        str(index),
                        "true",
                    ]
                )
                + ")"
            )
    if product_rows:
        rows.append(
            "INSERT INTO public.products (slug, name, description, brand_id, category_id, "
            "mrp_paise, price_paise, unit_label, stock, low_stock_threshold, images, tags, "
            "rating, is_active) VALUES\n"
            + ",\n".join(product_rows)
            + "\nON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, "
            "brand_id = EXCLUDED.brand_id, category_id = EXCLUDED.category_id, "
            "mrp_paise = EXCLUDED.mrp_paise, price_paise = EXCLUDED.price_paise, "
            "unit_label = EXCLUDED.unit_label, stock = EXCLUDED.stock, tags = EXCLUDED.tags, "
            "rating = EXCLUDED.rating, is_active = true;"
        )
    if variant_rows:
        rows.append(
            "INSERT INTO public.product_variants "
            "(product_id, label, mrp_paise, price_paise, stock, sort_order, is_active) VALUES\n"
            + ",\n".join(variant_rows)
            + "\nON CONFLICT (product_id, label) DO UPDATE SET mrp_paise = EXCLUDED.mrp_paise, "
            "price_paise = EXCLUDED.price_paise, stock = EXCLUDED.stock, "
            "sort_order = EXCLUDED.sort_order, is_active = true;"
        )
    return "\n\n".join(rows) + "\n"


def build_settings_sql() -> str:
    settings = get_settings()
    return (
        "UPDATE public.store_settings SET "
        f"store_name = {_quote(settings.STORE_NAME)}, "
        f"store_phone = {_quote(settings.STORE_PHONE)}, "
        f"store_address = {_quote(settings.STORE_ADDRESS)}, "
        f"store_maps_url = {_quote(settings.STORE_MAPS_URL)}, "
        f"feedback_email = {_quote(settings.FEEDBACK_EMAIL)}, "
        f"notification_email = {_quote(settings.FEEDBACK_EMAIL)} "
        "WHERE id = 1;"
    )


def catalogue_payload() -> dict[str, object]:
    """The whole catalogue as JSON — the form the database loader consumes.

    Committed at ``seeds/catalogue.json`` so a hosted database can load it without
    the API holding a database password (see ``seeds/README.md``).
    """
    categories: list[dict[str, object]] = []
    for category in data.CATEGORIES:
        categories.append(
            {
                "slug": category.slug,
                "name": category.name,
                "emoji": category.emoji,
                "sort_order": category.sort_order,
                "description": category.description,
                "parent_slug": None,
            }
        )
        for child_slug, child_name, child_order in category.children:
            categories.append(
                {
                    "slug": child_slug,
                    "name": child_name,
                    "emoji": None,
                    "sort_order": child_order,
                    "description": f"{child_name} at MSG Store",
                    "parent_slug": category.slug,
                }
            )

    products: list[dict[str, object]] = []
    for product in data.PRODUCTS:
        mrp, price = display_prices(product)
        parent_stock = 0 if product.variants else product.stock
        products.append(
            {
                "slug": product.slug,
                "name": product.name,
                "description": product.description
                or f"{product.name} from Tripat Pansari · MSG Store.",
                "brand_slug": product.brand,
                "category_slug": product.category,
                "mrp_paise": paise(mrp),
                "price_paise": paise(price),
                "unit_label": product.unit,
                "stock": parent_stock,
                "tags": list(product.tags),
                "rating": product.rating,
                "variants": [
                    {
                        "label": variant.label,
                        "mrp_paise": paise(variant.mrp),
                        "price_paise": paise(variant.price),
                        "stock": variant.stock,
                        "sort_order": index,
                    }
                    for index, variant in enumerate(product.variants)
                ],
            }
        )

    return {
        "version": 1,
        "generated_by": "apps/api/app/scripts/seed.py",
        "categories": categories,
        "brands": [{"slug": brand.slug, "name": brand.name} for brand in data.BRANDS],
        "products": products,
    }


def build_sql() -> str:
    """Generate idempotent SQL for the whole seed catalogue."""
    statements: list[str] = [
        "-- Generated by app/scripts/seed.py — idempotent catalogue seed.",
        "BEGIN;",
        "SELECT set_config('search_path', 'public, extensions, pg_temp', true);",
    ]

    # --- categories -----------------------------------------------------------
    for category in data.CATEGORIES:
        statements.append(
            f"""
INSERT INTO public.categories (slug, name, emoji, sort_order, description, parent_id, is_active)
VALUES ({_quote(category.slug)}, {_quote(category.name)}, {_quote(category.emoji)},
        {category.sort_order}, {_quote(category.description)}, NULL, true)
ON CONFLICT (slug) DO UPDATE
   SET name = EXCLUDED.name, emoji = EXCLUDED.emoji,
       sort_order = EXCLUDED.sort_order, description = EXCLUDED.description,
       is_active = true;""".strip()
        )
        for child_slug, child_name, child_order in category.children:
            statements.append(
                f"""
INSERT INTO public.categories (slug, name, sort_order, description, parent_id, is_active)
VALUES ({_quote(child_slug)}, {_quote(child_name)}, {child_order},
        {_quote(child_name + ' at MSG Store')},
        (SELECT id FROM public.categories WHERE slug = {_quote(category.slug)}), true)
ON CONFLICT (slug) DO UPDATE
   SET name = EXCLUDED.name, sort_order = EXCLUDED.sort_order,
       parent_id = EXCLUDED.parent_id, is_active = true;""".strip()
            )

    # --- brands ---------------------------------------------------------------
    for brand in data.BRANDS:
        statements.append(
            f"""
INSERT INTO public.brands (slug, name, is_active)
VALUES ({_quote(brand.slug)}, {_quote(brand.name)}, true)
ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, is_active = true;""".strip()
        )

    # --- products -------------------------------------------------------------
    for product in data.PRODUCTS:
        variants = list(product.variants)
        # A product with variants carries its stock on the variants; the parent
        # keeps the low-stock threshold and zero stock so totals are never double counted.
        parent_stock = 0 if variants else product.stock
        mrp, price = display_prices(product)
        description = product.description or f"{product.name} from Tripat Pansari · MSG Store."
        statements.append(
            f"""
INSERT INTO public.products (
    slug, name, description, brand_id, category_id, mrp_paise, price_paise,
    unit_label, stock, low_stock_threshold, images, tags, rating, is_active
) VALUES (
    {_quote(product.slug)}, {_quote(product.name)}, {_quote(description)},
    {brand_ref(product.brand)},
    (SELECT id FROM public.categories WHERE slug = {_quote(product.category)}),
    {paise(mrp)}, {paise(price)}, {_quote(product.unit)}, {parent_stock}, 10,
    '{{}}'::text[], {_text_array(list(product.tags))}, {product.rating}, true
)
ON CONFLICT (slug) DO UPDATE
   SET name = EXCLUDED.name, description = EXCLUDED.description,
       brand_id = EXCLUDED.brand_id, category_id = EXCLUDED.category_id,
       mrp_paise = EXCLUDED.mrp_paise, price_paise = EXCLUDED.price_paise,
       unit_label = EXCLUDED.unit_label, stock = EXCLUDED.stock,
       tags = EXCLUDED.tags, rating = EXCLUDED.rating, is_active = true;""".strip()
        )
        for index, variant in enumerate(variants):
            statements.append(
                f"""
INSERT INTO public.product_variants (
    product_id, label, mrp_paise, price_paise, stock, sort_order, is_active
) VALUES (
    (SELECT id FROM public.products WHERE slug = {_quote(product.slug)}),
    {_quote(variant.label)}, {paise(variant.mrp)}, {paise(variant.price)},
    {variant.stock}, {index}, true
)
ON CONFLICT (product_id, label) DO UPDATE
   SET mrp_paise = EXCLUDED.mrp_paise, price_paise = EXCLUDED.price_paise,
       stock = EXCLUDED.stock, sort_order = EXCLUDED.sort_order, is_active = true;""".strip()
            )

    # --- store identity (contact details come from the operator) -------------
    settings = get_settings()
    statements.append(
        f"""
UPDATE public.store_settings SET
    store_name = {_quote(settings.STORE_NAME)},
    store_phone = {_quote(settings.STORE_PHONE)},
    store_address = {_quote(settings.STORE_ADDRESS)},
    store_maps_url = {_quote(settings.STORE_MAPS_URL)},
    feedback_email = {_quote(settings.FEEDBACK_EMAIL)},
    notification_email = {_quote(settings.FEEDBACK_EMAIL)}
WHERE id = 1;""".strip()
    )
    statements.append("COMMIT;")
    return "\n\n".join(statements) + "\n"


async def apply_sql(sql: str) -> None:
    from sqlalchemy import text

    from app.db.session import dispose_engine, get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # `text()` executes the whole script inside one transaction.
        for chunk in [c.strip() for c in sql.split(";") if c.strip()]:
            if chunk.startswith("--"):
                chunk = "\n".join(
                    line for line in chunk.splitlines() if not line.strip().startswith("--")
                ).strip()
            if chunk:
                await session.execute(text(chunk))
        await session.commit()
    await dispose_engine()


async def ensure_admin_roles() -> int:
    """Grant admin to every ADMIN_EMAILS profile that already exists."""
    from sqlalchemy import text

    from app.db.session import dispose_engine, get_sessionmaker

    emails = get_settings().admin_emails
    if not emails:
        return 0
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(
            text(
                "UPDATE public.profiles SET role = 'admin', updated_at = now() "
                "WHERE lower(email) = ANY(:emails) AND role <> 'admin'"
            ),
            {"emails": emails},
        )
        await session.commit()
        count = int(getattr(result, "rowcount", 0) or 0)
    await dispose_engine()
    return count


async def create_staging_users() -> None:
    """Create the staging logins through the Supabase Admin API.

    Only used outside production and only when service-role credentials exist.
    Passwords are generated per run and printed once — never stored in the repo.
    """
    import secrets

    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    if settings.is_production:
        raise SystemExit("refusing to create staging users in production")
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        logger.warning("staging_users_skipped", reason="supabase credentials missing")
        return

    users = [
        ("customer.staging@tripatpansari.in", "Customer Staging", "customer"),
        ("friend.staging@tripatpansari.in", "Friend Staging", "customer"),
    ]
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        for email, name, role in users:
            password = secrets.token_urlsafe(12)
            response = await client.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users",
                headers=headers,
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": name},
                },
            )
            if response.status_code in (200, 201):
                print(f"  created {role}: {email} / {password}")
            else:
                print(f"  skipped {email}: {response.status_code} {response.text[:120]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the MSG Store catalogue")
    parser.add_argument("--print-sql", action="store_true", help="print SQL and exit")
    parser.add_argument("--print-json", action="store_true", help="print the catalogue JSON")
    parser.add_argument(
        "--format",
        choices=("readable", "compact"),
        default="readable",
        help="readable = one statement per row; compact = multi-row inserts",
    )
    parser.add_argument("--skip", type=int, default=0, help="skip N products (chunked apply)")
    parser.add_argument("--limit", type=int, default=0, help="apply at most N products")
    parser.add_argument("--with-users", action="store_true", help="also create staging logins")
    parser.add_argument("--admins", action="store_true", help="only sync admin roles")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.LOG_LEVEL, json_logs=not settings.is_local)

    if settings.is_production:
        print(
            "refusing to seed: ENVIRONMENT=production. "
            "Use admin tools or a reviewed SQL change instead.",
            file=sys.stderr,
        )
        return 2

    if args.print_json:
        import json

        print(json.dumps(catalogue_payload(), ensure_ascii=False, indent=1))
        return 0

    if args.print_sql:
        if args.format == "readable":
            print(build_sql())
        else:
            start = args.skip
            stop = start + args.limit if args.limit else None
            chunk = data.PRODUCTS[start:stop]
            print(
                build_compact_sql(products=chunk, include_reference=start == 0)
                + (build_settings_sql() if stop is None or stop >= len(data.PRODUCTS) else "")
            )
        return 0

    if args.admins:
        changed = asyncio.run(ensure_admin_roles())
        print(f"admin roles updated: {changed}")
        return 0

    asyncio.run(apply_sql(build_sql()))
    print(
        f"catalogue seeded: {len(data.CATEGORIES)} categories, "
        f"{len(data.BRANDS)} brands, {len(data.PRODUCTS)} products"
    )
    changed = asyncio.run(ensure_admin_roles())
    if changed:
        print(f"admin roles updated: {changed}")
    if args.with_users:
        asyncio.run(create_staging_users())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
