"""Store settings singleton access."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import StoreSettings

SINGLETON_ID = 1


async def get_settings_row(session: AsyncSession) -> StoreSettings | None:
    return await session.get(StoreSettings, SINGLETON_ID)
