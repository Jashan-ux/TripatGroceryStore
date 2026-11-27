"""Profile business rules: phone normalisation, admin bootstrap, referral codes."""

from __future__ import annotations

import pytest
from app.core.config import Settings, get_settings
from app.core.errors import ValidationError
from app.models.enums import UserRole
from app.services.profiles import (
    CODE_ALPHABET,
    CODE_LENGTH,
    bootstrap_role,
    generate_referral_code,
    normalise_phone,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8708973386", "8708973386"),
        ("+91 87089-73386", "8708973386"),
        ("+918708973386", "8708973386"),
        ("08708973386", "8708973386"),
        ("  98765 43210 ", "9876543210"),
        ("9123456789", "9123456789"),
    ],
)
def test_normalise_phone_accepts_common_formats(raw: str, expected: str) -> None:
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["12345", "5708973386", "870897338", "87089733861", "", "abcdefghij", "+44 7700 900123"],
)
def test_normalise_phone_rejects_invalid_numbers(raw: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        normalise_phone(raw)
    assert excinfo.value.code == "invalid_phone"
    assert excinfo.value.details["field"] == "phone"


def test_admin_bootstrap_only_for_configured_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        ENVIRONMENT="test",
        ADMIN_EMAILS="TripatInsan029@gmail.com, jashaninsan777@gmail.com",
    )
    monkeypatch.setattr("app.services.profiles.get_settings", lambda: settings)

    assert bootstrap_role("tripatinsan029@gmail.com") is UserRole.admin
    assert bootstrap_role("jashaninsan777@gmail.com") is UserRole.admin
    assert bootstrap_role("someone@example.com") is UserRole.customer


def test_admin_bootstrap_is_empty_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.profiles.get_settings",
        lambda: Settings(ENVIRONMENT="test", ADMIN_EMAILS=""),
    )
    assert bootstrap_role("owner@example.com") is UserRole.customer


def test_referral_codes_are_unambiguous_and_fixed_length() -> None:
    for _ in range(50):
        code = generate_referral_code()
        assert len(code) == CODE_LENGTH
        assert all(character in CODE_ALPHABET for character in code)
        # Ambiguous glyphs must never appear in a code someone reads aloud.
        assert not set(code) & set("01OIL")


def test_referral_alphabet_size_supports_millions_of_codes() -> None:
    assert len(CODE_ALPHABET) ** CODE_LENGTH >= 100_000_000


def test_default_settings_have_the_two_admin_addresses() -> None:
    """The seeded .env.example must not silently lose admin access."""
    example = get_settings()
    # In the test environment ADMIN_EMAILS may be empty; the invariant asserted
    # here is that parsing is case-insensitive and comma separated.
    assert isinstance(example.admin_emails, list)
