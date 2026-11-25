"""Database engine and session management.

Two URLs exist on purpose:

* ``DATABASE_URL`` — the Supabase **transaction-mode pooler**, used by the app.
  Transaction pooling cannot keep prepared statements between transactions, so
  asyncpg's statement cache is switched off (``statement_cache_size=0``), so
  nothing may rely on server-side prepared statements.
* ``DATABASE_DIRECT_URL`` — the direct connection, used by Alembic only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _engine_kwargs() -> dict[str, Any]:
    settings = get_settings()
    connect_args: dict[str, Any] = {
        # Required for Supabase pooler transaction mode.
        "statement_cache_size": 0,
        "server_settings": {
            "application_name": "tripat-api",
            "jit": "off",
            "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
        },
    }
    return {
        "pool_pre_ping": True,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": 1800,
        "connect_args": connect_args,
        "echo": False,
    }


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        _engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs())
        _sessionmaker = async_sessionmaker(
            _engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


async def ping_database() -> bool:
    """Cheap liveness probe used by /healthz."""
    from sqlalchemy import text

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - depends on infra
        logger.warning("database_ping_failed", error=str(exc))
        return False
