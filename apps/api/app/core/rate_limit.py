"""Rate limiting.

slowapi wraps limits, but the storage backend matters: an in-process counter
resets on every deploy and is per-instance, so production requires Redis
(Upstash-compatible). Boot fails in production when rate limiting is on and
``REDIS_URL`` is missing — see ``Settings._validate_runtime``.

The key is the authenticated user id when present, else the client IP. Behind
Vercel/Render the client IP arrives via the platform proxy header, which
uvicorn's ``--proxy-headers`` already applies to ``request.client``.
"""

from __future__ import annotations

from collections.abc import Callable

from starlette.requests import Request

from app.core.config import get_settings

_remote_address: Callable[[Request], str] | None
_Limiter: Callable[..., object] | None
try:  # pragma: no cover - the import guard keeps the app importable without slowapi
    from slowapi import Limiter as _SlowapiLimiter
    from slowapi.util import get_remote_address as _slowapi_remote_address

    _Limiter = _SlowapiLimiter
    _remote_address = _slowapi_remote_address
except Exception:  # pragma: no cover
    _Limiter = None
    _remote_address = None


def rate_limit_key(request: Request) -> str:
    """Identify the caller: user id when authenticated, otherwise IP."""
    user = getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    if user_id:
        return f"user:{user_id}"
    if _remote_address is None:  # pragma: no cover - slowapi missing
        return "anonymous"
    return f"ip:{_remote_address(request)}"


def build_limiter() -> object | None:
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED or _Limiter is None:
        return None
    storage = settings.REDIS_URL or "memory://"
    return _Limiter(
        key_func=rate_limit_key,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
        storage_uri=storage,
        headers_enabled=True,
        strategy="fixed-window",
    )


limiter = build_limiter()
