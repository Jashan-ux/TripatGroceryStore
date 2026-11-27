from __future__ import annotations

import pytest
from app.core.config import Settings, validate_pincode


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATABASE_URL",
        "DATABASE_DIRECT_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "STORE_MAPS_URL",
        "RESEND_API_KEY",
        "REDIS_URL",
        "ADMIN_EMAILS",
        "CORS_EXTRA_ORIGINS",
        "WEB_ORIGIN",
        "RATE_LIMIT_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)


def test_production_requires_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None)  # type: ignore[call-arg]
    message = str(excinfo.value)
    assert "DATABASE_URL is required in production" in message
    assert "ADMIN_EMAILS is required in production" in message


def test_production_requires_https_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("WEB_ORIGIN", "http://insecure.example")
    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "WEB_ORIGIN must use https" in str(excinfo.value)


def test_wildcard_cors_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    settings = Settings(_env_file=None, WEB_ORIGIN="http://localhost:5173", CORS_EXTRA_ORIGINS="*")
    assert "*" not in settings.cors_origins
    assert settings.cors_origins == ["http://localhost:5173"]


def test_cors_origins_normalise_canonical_apex_and_preview_urls() -> None:
    settings = Settings(
        _env_file=None,
        WEB_ORIGIN="https://www.tripatmsg.in/",
        CORS_EXTRA_ORIGINS=(
            "https://tripatmsg.in, "
            "https://tripat-grocery-store-git-arena-660db-528c3e-jashan-uxs-projects.vercel.app/"
        ),
    )

    assert settings.cors_origins == [
        "https://www.tripatmsg.in",
        "https://tripatmsg.in",
        "https://tripat-grocery-store-git-arena-660db-528c3e-jashan-uxs-projects.vercel.app",
    ]


def test_jwks_and_issuer_derived_from_supabase_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    settings = Settings(_env_file=None, SUPABASE_URL="https://abc.supabase.co/")
    assert settings.jwt_issuer == "https://abc.supabase.co/auth/v1"
    assert settings.jwks_url == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"


def test_public_config_never_contains_service_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        SUPABASE_URL="https://abc.supabase.co",
        SUPABASE_ANON_KEY="anon-key",
        SUPABASE_SERVICE_ROLE_KEY="super-secret-service-role",
        STORE_MAPS_URL="https://maps.app.goo.gl/short",
    )
    public = settings.public_config()
    assert "super-secret-service-role" not in str(public)
    assert public["supabase_anon_key"] == "anon-key"
    assert public["store_maps_url"] == "https://maps.app.goo.gl/short"


def test_admin_emails_are_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    settings = Settings(_env_file=None, ADMIN_EMAILS=" Owner@Example.COM , ,")
    assert settings.admin_emails == ["owner@example.com"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("125104", True), ("125201", True), ("12510", False), ("1251041", False), ("abc123", False)],
)
def test_pincode_validation(value: str, expected: bool) -> None:
    assert validate_pincode(value) is expected
