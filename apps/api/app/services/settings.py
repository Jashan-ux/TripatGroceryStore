"""Store settings: the single source of every business number and contact detail."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.catalogue import StoreSettings
from app.repositories import settings as repo

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 30
_cache: tuple[float, StoreSettings] | None = None


def invalidate_cache() -> None:
    global _cache
    _cache = None


def _from_env() -> StoreSettings:
    """Fallback used before the database is reachable (health checks, first boot)."""
    settings = get_settings()
    return StoreSettings(
        id=1,
        store_name=settings.STORE_NAME,
        store_phone=settings.STORE_PHONE,
        store_address=settings.STORE_ADDRESS,
        store_maps_url=settings.STORE_MAPS_URL,
        feedback_email=settings.FEEDBACK_EMAIL,
        store_open=True,
    )


def _detach(row: StoreSettings) -> StoreSettings:
    """Copy the row into a transient instance with every column already loaded.

    Caching the live ORM object is a trap: a later ``rollback()`` in whatever
    request happened to load it expires its attributes, and every other request
    inside the cache window then raises ``DetachedInstanceError``. A transient
    copy has no session to miss, so reading it can never trigger a refresh.
    """
    columns = {attr.key: getattr(row, attr.key) for attr in sa_inspect(row).mapper.column_attrs}
    values: dict[str, Any] = columns
    if isinstance(values.get("serviceable_pincodes"), list):
        # Copy the list too: the cached snapshot must not share mutable state.
        values = {**values, "serviceable_pincodes": list(values["serviceable_pincodes"])}
    return StoreSettings(**values)


async def get_store_settings(session: AsyncSession) -> StoreSettings:
    """Read the singleton row, with a short in-process cache.

    A 30-second cache means the merchant's edits apply on the next checkout
    without a redeploy, while public pages do not hit the table on every request.
    """
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL_SECONDS:
        return _cache[1]
    row = await repo.get_settings_row(session)
    if row is None:  # pragma: no cover - the migration inserts it
        logger.warning("store_settings_missing")
        return _from_env()
    snapshot = _detach(row)
    _cache = (now, snapshot)
    return snapshot
