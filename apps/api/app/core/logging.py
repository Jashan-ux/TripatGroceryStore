"""Structured logging setup.

Logs are JSON in staging/production and human-readable locally. A strict
deny-list of keys keeps PII out of logs: the redaction processor walks every
event dict and blanks values under sensitive key names, and it truncates
values that look like bearer tokens or JWTs anywhere in a message.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
_EMAIL = re.compile(r"([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]+)")
_PHONE = re.compile(r"\+?\d{10,13}")

REDACT_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "set-cookie",
    "api_key",
    "apikey",
    "secret",
    "service_role",
    "otp",
    "code",
    "line1",
    "line2",
    "landmark",
    "address",
    "full_address",
    "phone",
    "email",
    "name",
}


def _scrub_text(value: str) -> str:
    value = _JWT.sub("[jwt]", value)
    value = _BEARER.sub("Bearer [redacted]", value)
    value = _EMAIL.sub(r"\1***\2", value)
    value = _PHONE.sub("[phone]", value)
    return value


def _redact(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        lower = key.lower()
        value = event_dict[key]
        if lower in REDACT_KEYS:
            event_dict[key] = "[redacted]"
        elif isinstance(value, str):
            event_dict[key] = _scrub_text(value)
    return event_dict


def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,
        structlog.processors.StackInfoRenderer(),
    ]
    processors: list[Any] = [
        *shared,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    # Silence uvicorn's duplicate access logs; we emit our own structured record.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").handlers = []


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
