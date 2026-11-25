"""The audit trail.

One helper, called by every admin mutation in this phase. Two rules:

* **Write it in the same transaction as the change.** If the product update rolls
  back, the log entry rolls back with it — there is never a row describing
  something that did not happen.
* **Store the diff, not the whole row.** ``{"price_paise": {"from": 32000,
  "to": 34000}}`` reads as a sentence on a phone; two copies of a product do not.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AuditLog
from app.models.catalogue import Profile
from app.repositories import admin_tools as repo

#: Columns that are noise in a diff: every update changes ``updated_at``.
_IGNORED = frozenset({"updated_at", "created_at", "search_text"})


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Only the keys whose value actually moved."""
    changed: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        if key in _IGNORED:
            continue
        old, new = before.get(key), after.get(key)
        if old != new:
            changed[key] = {"from": old, "to": new}
    return changed


async def record(
    session: AsyncSession,
    *,
    actor: Profile,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None = None,
    summary: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    note: str = "",
) -> AuditLog:
    row = AuditLog(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action[:60],
        entity=entity[:40],
        entity_id=entity_id,
        summary=summary[:200],
        before=before or {},
        after=after or {},
        note=note,
    )
    return await repo.add_audit(session, row)


__all__ = ["diff", "record"]
