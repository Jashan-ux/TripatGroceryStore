"""Logs must never carry PII, tokens or full addresses (ASVS V9 / DPDP)."""

from __future__ import annotations

import json

import structlog
from app.core.logging import _redact, _scrub_text, configure_logging
from pytest import CaptureFixture


def test_jwt_is_scrubbed_from_messages() -> None:
    # jwt.io's public sample token, assembled from parts: a literal
    # three-segment token here would be flagged by secret scanners forever.
    token = ".".join(
        [
            "eyJhbGciOiJIUzI1NiJ9",
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0",
            "dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
        ]
    )
    scrubbed = _scrub_text(f"auth header was Bearer {token}")
    assert token not in scrubbed
    assert "eyJ" not in scrubbed


def test_email_and_phone_are_masked() -> None:
    assert _scrub_text("owner@example.com failed") == "o***@example.com failed"
    assert "[phone]" in _scrub_text("call 9876543210 now")


def test_sensitive_keys_are_redacted_entirely() -> None:
    event = {
        "event": "order_placed",
        "email": "customer@example.com",
        "phone": "9876543210",
        "line1": "House 42, Street 9",
        "password": "hunter2",
        "authorization": "Bearer abc",
        "order_no": "TP-000123",
    }
    result = _redact(None, None, event)
    assert result["email"] == "[redacted]"
    assert result["phone"] == "[redacted]"
    assert result["line1"] == "[redacted]"
    assert result["password"] == "[redacted]"
    assert result["authorization"] == "[redacted]"
    # Non-sensitive operational fields survive for debugging.
    assert result["order_no"] == "TP-000123"
    assert result["event"] == "order_placed"


def test_logged_event_is_json_without_pii(capsys: CaptureFixture[str]) -> None:
    configure_logging("INFO", json_logs=True)
    logger = structlog.get_logger("test")
    logger.info(
        "order_placed",
        email="customer@example.com",
        access_token="secret-token",
        order_no="TP-000123",
    )
    line = next(
        (ln for ln in capsys.readouterr().out.splitlines() if "order_placed" in ln),
        None,
    )
    assert line, "no log event captured"
    payload = json.loads(line)
    serialized = json.dumps(payload)
    assert "customer@example.com" not in serialized
    assert "secret-token" not in serialized
    assert payload.get("order_no") == "TP-000123"
    assert payload.get("level") == "info"
