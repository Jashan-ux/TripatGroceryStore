"""Catalogue presentation rules that do not need a database."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field
from decimal import Decimal

import pytest
from app.services.catalogue import CategoryNode, discount_percent, effective_stock, rating_value


@pytest.mark.parametrize(
    ("mrp", "price", "expected"),
    [
        (19_500, 18_000, 8),
        (100, 100, 0),
        (100, 120, 0),  # price above MRP never shows a negative discount
        (0, 0, 0),
        (29_500, 27_800, 6),
        (10_000, 1, 100),
    ],
)
def test_discount_percent(mrp: int, price: int, expected: int) -> None:
    assert discount_percent(mrp, price) == expected


@dataclass
class FakeVariant:
    stock: int
    is_active: bool = True


@dataclass
class FakeProduct:
    stock: int
    variants: list[FakeVariant] = field(default_factory=list)


def test_effective_stock_uses_active_variants_when_present() -> None:
    product = FakeProduct(
        stock=0, variants=[FakeVariant(4), FakeVariant(6), FakeVariant(99, is_active=False)]
    )
    assert effective_stock(product) == 10  # type: ignore[arg-type]


def test_effective_stock_falls_back_to_product_stock() -> None:
    assert effective_stock(FakeProduct(stock=7)) == 7  # type: ignore[arg-type]


def test_effective_stock_never_goes_negative() -> None:
    product = FakeProduct(stock=-3, variants=[FakeVariant(-2), FakeVariant(0)])
    assert effective_stock(product) == 0  # type: ignore[arg-type]


def test_rating_value_handles_none_and_decimal() -> None:
    assert rating_value(None) == 0.0  # type: ignore[arg-type]
    assert rating_value(Decimal("4.5")) == 4.5
    assert rating_value(4) == 4.0


def test_category_node_is_immutable() -> None:
    node = CategoryNode(category=object(), children=(), product_count=0)  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        node.product_count = 5  # type: ignore[misc]
