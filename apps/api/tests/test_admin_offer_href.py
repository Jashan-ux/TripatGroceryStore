"""Security checks for admin-authored offer deep links."""

import pytest
from app.schemas.admin_ops import OfferIn
from pydantic import ValidationError


@pytest.mark.parametrize(
    "href",
    [
        "https://attacker.example/",
        "//attacker.example/",
        "/\\attacker.example/",
        "/safe\\@attacker.example/",
        "/search?q=tea\nLocation: https://attacker.example",
    ],
)
def test_offer_href_rejects_external_or_ambiguous_urls(href: str) -> None:
    with pytest.raises(ValidationError):
        OfferIn(title="A special offer", href=href)


def test_offer_href_accepts_internal_path_and_query() -> None:
    offer = OfferIn(title="A special offer", href="/search?q=tea&sort=popular")

    assert offer.href == "/search?q=tea&sort=popular"
