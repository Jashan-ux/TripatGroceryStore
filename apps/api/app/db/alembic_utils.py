"""Helpers shared with Alembic's autogenerate environment."""

from __future__ import annotations

from typing import Any


def include_object(
    object: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any | None,
) -> bool:
    """Ignore reflected FKs into Supabase's external ``auth`` schema.

    Supabase owns ``auth.users`` and the FK from ``public.profiles.id`` is
    installed by a hand-written migration. The target table is intentionally
    outside ``Base.metadata`` and Alembic is configured with ``include_schemas``
    disabled, so autogenerate otherwise misreports that external FK as removed.
    This filter is deliberately narrow: ordinary public-schema FKs continue to
    participate in autogenerate comparisons.
    """
    del name, compare_to
    if type_ != "foreign_key_constraint" or not reflected:
        return True

    for element in getattr(object, "elements", ()):
        target = getattr(element, "target_fullname", "")
        parts = [part.strip('"') for part in target.split(".")]
        if len(parts) >= 3 and parts[-3] == "auth":
            return False
    return True
