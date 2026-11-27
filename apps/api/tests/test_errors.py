from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"]


def test_validation_error_lists_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/config",
        json={"unexpected": "value"},
    )
    assert response.status_code in {405, 422}
    if response.status_code == 422:
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert isinstance(error["details"]["fields"], list)


def test_wrong_method_is_rejected_with_shape(client: TestClient) -> None:
    response = client.delete("/healthz")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_docs_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setenv("STORE_MAPS_URL", "https://maps.app.goo.gl/xyz")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    monkeypatch.setenv("WEB_ORIGIN", "https://msgstore.example")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.is_production

    from app.main import create_app

    prod_app = create_app()
    assert prod_app.docs_url is None
    assert prod_app.openapi_url is None
    assert prod_app.redoc_url is None
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()


def test_openapi_schema_is_generated(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["openapi"].startswith("3.")
    assert "/healthz" in schema["paths"]
    assert "/api/v1/status" in schema["paths"]


def test_error_class_maps_to_response(client: TestClient) -> None:
    from app.core.errors import ConflictError

    err = ConflictError("Already placed", code="duplicate_order", details={"order_no": "TP-0001"})
    assert err.status_code == 409
    assert err.code == "duplicate_order"
    assert err.details["order_no"] == "TP-0001"
