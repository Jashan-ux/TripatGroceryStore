"""Private browser subscription input; no read endpoint ever returns these keys."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class PushKeysIn(APIModel):
    p256dh: str = Field(min_length=32, max_length=200)
    auth: str = Field(min_length=16, max_length=100)


class PushSubscriptionIn(APIModel):
    endpoint: str = Field(min_length=1, max_length=4096)
    keys: PushKeysIn
    expiration_time: datetime | None = None

    @field_validator("endpoint")
    @classmethod
    def endpoint_must_be_https(cls, value: str) -> str:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower().rstrip(".")
        if parts.scheme != "https" or not host or parts.username or parts.password:
            raise ValueError("Push endpoint must be an HTTPS URL.")
        try:
            port = parts.port
        except ValueError as exc:
            raise ValueError("Push endpoint has an invalid port.") from exc
        if port not in {None, 443}:
            raise ValueError("Push endpoint must use the standard HTTPS port.")
        provider_host = (
            host == "fcm.googleapis.com"
            or host == "web.push.apple.com"
            or host == "push.services.mozilla.com"
            or host.endswith(".push.services.mozilla.com")
            or host.endswith(".notify.windows.com")
        )
        if not provider_host:
            raise ValueError("Push endpoint must belong to a supported browser push provider.")
        return value


class PushSubscriptionOut(APIModel):
    enabled: bool
    message: str
