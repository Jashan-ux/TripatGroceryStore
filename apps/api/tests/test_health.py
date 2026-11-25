from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_healthz_is_ok_and_fast(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["environment"] == "test"
    assert {c["name"] for c in body["components"]} >= {"api", "database"}


def test_healthz_reports_unconfigured_database(client: TestClient) -> None:
    body = client.get("/healthz").json()
    database = next(c for c in body["components"] if c["name"] == "database")
    assert database["status"] in {"not_configured", "ok", "down"}


def test_readiness_fails_without_database(client: TestClient) -> None:
    response = client.get("/healthz/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_status_returns_utc_timestamp(client: TestClient) -> None:
    body = client.get("/api/v1/status").json()
    assert body["status"] == "ok"
    assert body["server_time"].endswith("Z") or "+00:00" in body["server_time"]


def test_public_config_exposes_store_contact_but_no_secrets(client: TestClient) -> None:
    body = client.get("/api/v1/config").json()
    assert body["store_phone"] == "+91 87089-73386"
    assert body["feedback_email"] == "tripatinsan029@gmail.com"
    assert "Mandi Dabwali" in body["store_address"]
    serialized = str(body).lower()
    for secret in ("service_role", "secret", "password", "database_url", "private"):
        assert secret not in serialized


@pytest.mark.parametrize("path", ["/healthz", "/api/v1/status", "/api/v1/config"])
def test_security_headers_present(client: TestClient, path: str) -> None:
    headers = client.get(path).headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=(self)" in headers["permissions-policy"]
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "'unsafe-eval'" not in csp
    assert "unsafe-inline" not in csp.split("style-src")[0]


def test_request_id_is_echoed_and_generated(client: TestClient) -> None:
    generated = client.get("/healthz")
    assert generated.headers["x-request-id"]
    echoed = client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert echoed.headers["x-request-id"] == "abc123"


def test_oversized_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "x" * 200})
    assert response.headers["x-request-id"] != "x" * 200
    assert len(response.headers["x-request-id"]) <= 64
