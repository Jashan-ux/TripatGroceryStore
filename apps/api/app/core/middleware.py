"""Request-id + access log + security headers middleware."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, bind log context, emit one structured access log."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        clear_contextvars()
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and len(incoming) <= 64 else uuid.uuid4().hex
        request.state.request_id = request_id
        bind_contextvars(request_id=request_id, path=request.url.path, method=request.method)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.warning("request_failed", duration_ms=elapsed_ms, status=500)
            raise
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            status=response.status_code,
            duration_ms=elapsed_ms,
            client=getattr(request.client, "host", None),
        )
        clear_contextvars()
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defence-in-depth headers for every response.

    CSP is deliberately strict: no inline scripts, no third-party scripts, only
    the Supabase origin and OpenStreetMap tiles are allowed outbound.
    """

    def __init__(self, app, **_: object) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        settings = get_settings()
        supabase = settings.SUPABASE_URL.rstrip("/")
        connect_extra = ""
        img_extra = "https://tile.openstreetmap.org https://*.tile.openstreetmap.org"
        if supabase:
            connect_extra = f" {supabase} wss://{supabase.split('://', 1)[-1]}"
            img_extra = f"{img_extra} {supabase}"
        self.csp = (
            "default-src 'self'; "
            f"connect-src 'self'{connect_extra}; "
            f"img-src 'self' data: blob: {img_extra}; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "script-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests"
        )
        self.hsts = "max-age=31536000; includeSubDomains; preload" if settings.is_production else ""
        self.is_production = settings.is_production

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["X-Frame-Options"] = "DENY"
        headers["Permissions-Policy"] = (
            "geolocation=(self), camera=(), microphone=(), payment=(), usb=()"
        )
        headers["Cross-Origin-Opener-Policy"] = "same-origin"
        headers["Cross-Origin-Resource-Policy"] = "same-origin"
        headers["Content-Security-Policy"] = self.csp
        if self.hsts:
            headers["Strict-Transport-Security"] = self.hsts
        # API payloads are private by default.
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")
        return response
