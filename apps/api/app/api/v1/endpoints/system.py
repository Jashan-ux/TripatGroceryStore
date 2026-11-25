"""Liveness, readiness and public runtime config.

`/healthz` is the container/orchestrator probe: it always answers fast and only
reports component detail. `/healthz/ready` is the deploy gate used by CI and
Render/Fly health checks: it returns 503 until the database answers.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app import __version__
from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.openapi import ERROR_RESPONSES
from app.db.session import ping_database
from app.schemas.common import HealthComponent, HealthResponse, PublicConfig, StatusResponse
from app.services.settings import get_store_settings

logger = get_logger(__name__)

router = APIRouter(tags=["system"], responses=ERROR_RESPONSES)

#: Root-level probes (no /api/v1 prefix) so platform health checks stay simple.
root_router = APIRouter(tags=["system"], responses=ERROR_RESPONSES)

_STARTED_AT = time.monotonic()


def _uptime() -> float:
    return round(time.monotonic() - _STARTED_AT, 3)


@root_router.get("/healthz", response_model=HealthResponse, summary="Liveness probe")
async def healthz() -> HealthResponse:
    settings = get_settings()
    components = [HealthComponent(name="api", status="ok")]
    db_status: str = "not_configured"
    if settings.DATABASE_URL:
        started = time.perf_counter()
        ok = await ping_database()
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        db_status = "ok" if ok else "down"
        components.append(
            HealthComponent(
                name="database",
                status="ok" if ok else "down",
                latency_ms=elapsed,
            )
        )
    else:
        components.append(HealthComponent(name="database", status="not_configured"))
    return HealthResponse(
        status="ok" if db_status in {"ok", "not_configured"} else "degraded",
        version=__version__,
        environment=settings.ENVIRONMENT,
        uptime_seconds=_uptime(),
        components=components,
    )


@root_router.get("/healthz/ready", response_model=HealthResponse, summary="Readiness probe")
async def readiness(response: Response) -> HealthResponse:
    settings = get_settings()
    ok = bool(settings.DATABASE_URL) and await ping_database()
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if ok else "degraded",
        version=__version__,
        environment=settings.ENVIRONMENT,
        uptime_seconds=_uptime(),
        components=[
            HealthComponent(name="api", status="ok"),
            HealthComponent(name="database", status="ok" if ok else "down"),
        ],
    )


@router.get("/status", response_model=StatusResponse, tags=["system"])
async def api_status() -> StatusResponse:
    return StatusResponse(server_time=datetime.now(tz=UTC))


@router.get("/config", response_model=PublicConfig, summary="Public runtime configuration")
async def public_config(session: SessionDep) -> PublicConfig:
    """Non-secret values the frontend needs (store contact, Supabase URL/anon key).

    Store contact comes from ``store_settings`` — the merchant can change the
    phone, address or Maps link without a deploy. If the database is not
    reachable yet (cold boot, health check) we fall back to the seeded env
    values so the storefront still renders a phone number.

    The anon key is public by design; the service-role key never leaves the server.
    """
    settings = get_settings()
    payload = settings.public_config()
    try:
        store = await get_store_settings(session)
    except Exception:  # pragma: no cover - database unavailable
        logger.warning("config_store_settings_unavailable")
        store = None
    if store is not None:
        payload.update(
            {
                "store_name": store.store_name,
                "store_phone": store.store_phone,
                "store_address": store.store_address,
                "store_maps_url": store.store_maps_url,
                "feedback_email": store.feedback_email,
                "minimum_order_paise": store.minimum_order_paise,
                "serviceable_pincodes": list(store.serviceable_pincodes),
                "default_delivery_days": store.default_delivery_days,
            }
        )
    return PublicConfig.model_validate(payload)
