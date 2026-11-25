"""Application factory.

Mount rules that matter for security and operations:

* ``/docs``, ``/redoc`` and ``/openapi.json`` are disabled in production — the
  schema is generated at build time into ``packages/api-client`` instead.
* All business routes live under ``/api/v1``; only ``/healthz`` (and its
  ``/ready`` variant) sit at the root, so an edge platform can probe without
  authentication.
* CORS is an explicit allowlist for local/preview development; in production the
  browser talks to the same origin through the Vercel rewrite, so no CORS is
  needed at all.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.endpoints.system import root_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.db.session import dispose_engine

logger = get_logger(__name__)

DESCRIPTION = """
REST API for **Tripat Pansari · MSG Store** — Mandi Dabwali, Haryana.

* Money is integer **paise**; timestamps are UTC (displayed in Asia/Kolkata).
* Every error uses one shape: `{"error": {"code", "message", "details", "request_id"}}`.
* Order placement requires an `Idempotency-Key` header.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL, json_logs=not settings.is_local)
    logger.info(
        "api_starting",
        version=__version__,
        environment=settings.ENVIRONMENT,
        rate_limiting=settings.RATE_LIMIT_ENABLED,
        rate_limit_window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    )
    started = time.monotonic()
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("api_stopped", uptime_seconds=round(time.monotonic() - started, 3))


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = not settings.is_production
    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
        swagger_ui_parameters={"persistAuthorization": True},
    )

    # Middleware (last added = outermost).
    # Starlette 1.10 types `add_middleware` as a factory of ASGI callables and
    # does not accept BaseHTTPMiddleware subclasses that override `__init__`.
    app.add_middleware(SecurityHeadersMiddleware)  # type: ignore[arg-type]
    app.add_middleware(RequestContextMiddleware)
    if not settings.is_production or settings.CORS_EXTRA_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-Request-ID",
                "X-Turnstile-Token",
            ],
            expose_headers=["X-Request-ID", "Retry-After"],
            max_age=600,
        )

    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(root_router)

    if settings.SENTRY_DSN and not settings.is_local:  # pragma: no cover - optional service
        _init_sentry(settings.SENTRY_DSN, settings.ENVIRONMENT)

    return app


def _init_sentry(dsn: str, environment: str) -> None:  # pragma: no cover
    """Sentry with PII scrubbing: no bodies, no headers, no user identifiers."""
    try:
        import sentry_sdk  # type: ignore[import-not-found]

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.05,
            send_default_pii=False,
            max_request_body_size="never",
            before_send=lambda event, hint: _scrub_event(event),
        )
    except ImportError:  # pragma: no cover
        logger.warning("sentry_not_installed")


def _scrub_event(event: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
    """Drop request bodies/headers and user identity before sending to Sentry."""
    event.pop("request", None)
    event.pop("user", None)
    event.pop("breadcrumbs", None)
    return event


app = create_app()
