"""Security headers (ASVS V7 / S‑09)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_csp_blocks_third_party_scripts(client: TestClient) -> None:
    csp = client.get("/healthz").headers["content-security-policy"]
    directives = {part.split(" ")[0]: part for part in csp.split("; ") if part}
    assert directives["default-src"] == "default-src 'self'"
    assert directives["script-src"] == "script-src 'self'"
    assert "unsafe-inline" not in directives["script-src"]
    assert "unsafe-eval" not in csp
    assert directives["object-src"] == "object-src 'none'"
    assert directives["frame-ancestors"] == "frame-ancestors 'none'"
    assert "upgrade-insecure-requests" in csp


def test_csp_allows_openstreetmap_tiles_and_supabase(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as local_client:
        csp = local_client.get("/healthz").headers["content-security-policy"]
    assert "tile.openstreetmap.org" in csp
    assert "https://abc.supabase.co" in csp
    get_settings.cache_clear()


def test_permissions_policy_allows_geolocation_only_for_self(client: TestClient) -> None:
    value = client.get("/healthz").headers["permissions-policy"]
    assert "geolocation=(self)" in value
    for blocked in ("camera=()", "microphone=()", "payment=()", "usb=()"):
        assert blocked in value


def test_hsts_only_in_production(client: TestClient) -> None:
    assert "strict-transport-security" not in client.get("/healthz").headers


def test_api_responses_are_not_cached(client: TestClient) -> None:
    assert client.get("/api/v1/status").headers["cache-control"] == "no-store"
    assert client.get("/api/v1/config").headers["cache-control"] == "no-store"


def test_no_server_header_leaks_version(client: TestClient) -> None:
    headers = client.get("/healthz").headers
    assert "uvicorn" not in headers.get("server", "").lower()


def test_cross_origin_isolation_headers(client: TestClient) -> None:
    headers = client.get("/healthz").headers
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert headers["cross-origin-resource-policy"] == "same-origin"
