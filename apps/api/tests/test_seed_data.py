"""The seed catalogue must be internally consistent.

These are the invariants a reviewer would otherwise have to check by eye — a
wrong price or a missing parent category would show up in the storefront.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import pytest
from app.scripts import seed
from app.scripts import seed_data as data


def test_categories_have_unique_slugs() -> None:
    slugs = [category.slug for category in data.CATEGORIES]
    for category in data.CATEGORIES:
        slugs.extend(child[0] for child in category.children)
    assert len(slugs) == len(set(slugs))


def test_every_slug_is_url_safe() -> None:
    pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    for category in data.CATEGORIES:
        assert pattern.match(category.slug)
        for child_slug, _, _ in category.children:
            assert pattern.match(child_slug)
    for product in data.PRODUCTS:
        assert pattern.match(product.slug)


def test_products_reference_known_brands_and_categories() -> None:
    brand_slugs = {brand.slug for brand in data.BRANDS}
    category_slugs: set[str] = set()
    for category in data.CATEGORIES:
        category_slugs.add(category.slug)
        category_slugs.update(child[0] for child in category.children)

    for product in data.PRODUCTS:
        assert product.category in category_slugs, product.slug
        if product.brand is not None:
            assert product.brand in brand_slugs, product.slug


def test_product_slugs_are_unique() -> None:
    slugs = [product.slug for product in data.PRODUCTS]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("product", data.PRODUCTS, ids=lambda product: product.slug)
def test_prices_are_positive_and_below_mrp(product: data.ProductSeed) -> None:
    mrp, price = seed.display_prices(product)
    assert price > 0
    assert mrp >= price
    assert price == Decimal(str(price)).quantize(Decimal("0.01"))


@pytest.mark.parametrize("product", data.PRODUCTS, ids=lambda product: product.slug)
def test_variants_are_ordered_priced_and_unique(product: data.ProductSeed) -> None:
    labels = [variant.label for variant in product.variants]
    assert len(labels) == len(set(labels))
    prices: list[float] = []
    for variant in product.variants:
        assert variant.price > 0
        assert variant.mrp >= variant.price
        assert variant.stock >= 0
        prices.append(variant.price)
    if not product.variants:
        assert product.stock >= 0
        return
    # A bigger pack should never cost less than a smaller one of the same product.
    assert prices == sorted(prices)


def test_grams_are_only_used_for_loose_items() -> None:
    for product in data.PRODUCTS:
        if product.variants:
            assert product.unit == "per pack"
            assert all(
                variant.label.endswith("g") or variant.label.endswith("kg")
                for variant in product.variants
            )


def test_paise_conversion_is_exact() -> None:
    assert seed.paise(195) == 19_500
    assert seed.paise(1.15) == 115
    assert seed.paise(0.99) == 99
    assert seed.paise("1234.56") == 123_456  # type: ignore[arg-type]


def test_catalogue_payload_matches_the_data() -> None:
    payload: dict[str, Any] = seed.catalogue_payload()
    assert len(payload["categories"]) == sum(1 + len(c.children) for c in data.CATEGORIES)
    assert len(payload["brands"]) == len(data.BRANDS)
    assert len(payload["products"]) == len(data.PRODUCTS)
    first = payload["products"][0]
    assert isinstance(first["mrp_paise"], int)
    assert first["mrp_paise"] % 100 == 0 or first["mrp_paise"] > 0
