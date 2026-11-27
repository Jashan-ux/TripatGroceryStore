"""Rate limits: the counters that protect the routes a stranger can reach.

Phase 5 shipped a limiter that existed but was never installed, and whose storage
was Redis — a service this deployment does not have. That combination is the
worst of both worlds: a documented intent the runtime ignores, and a production
boot that fails unless the owner buys a cache. This module replaces it with
something that runs: a **fixed window counted in Postgres**.

How it works, in one paragraph. Every window is aligned to the clock
(``window_start = floor(now / window) * window``), which means two workers in two
containers agree on where the window begins without talking to each other. Each
hit is one upsert; the returned ``hits`` decides allow or deny; ``window_end``
decides what ``Retry-After`` says. Because the counter is committed before the
endpoint runs, **failed attempts still count** — that is the whole point for a
route like "use a friend's code", where the attack is trying many wrong codes.

Two behaviours are deliberate and worth stating plainly:

* **Fail open.** If the counter cannot be written (database down, table missing)
  the request is allowed and a warning is logged. A limiter that takes the shop
  down when its own bookkeeping hiccups is worse than no limiter; the endpoints
  behind it are all authorised and validated anyway.
* **Zero means off.** Setting a route's limit to 0 disables that one route,
  which is what ``RATE_LIMIT_ENABLED=false`` does for all of them — the test
  suite runs that way so its hundreds of requests are not fighting a budget.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitedError
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Dead rows are swept on roughly one call in this many, rather than by a cron.
SWEEP_ONE_IN = 50
#: A window's rows are kept this long after it closes, so a delay cannot hide them.
SWEEP_GRACE = timedelta(hours=1)

#: Scope → the settings field holding its per-window allowance.
_LIMIT_FIELDS: dict[str, str] = {
    "feedback": "RATE_LIMIT_FEEDBACK",
    "orders": "RATE_LIMIT_ORDERS",
    "quote": "RATE_LIMIT_QUOTE",
    "referral": "RATE_LIMIT_REFERRAL",
    "scratch": "RATE_LIMIT_SCRATCH",
    "uploads": "RATE_LIMIT_UPLOADS",
    "push": "RATE_LIMIT_PUSH",
}


@dataclass(frozen=True, slots=True)
class Rule:
    """One route's allowance: N hits per aligned window."""

    scope: str
    limit: int
    window_seconds: int
    #: ``RATE_LIMIT_ENABLED`` — one switch for the whole deployment.
    switched_on: bool = True

    @property
    def enabled(self) -> bool:
        return self.switched_on and self.limit > 0 and self.window_seconds > 0


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome of one hit."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    window_end: datetime


def counter_sessionmaker() -> Any:
    """The session factory the counters use.

    A seam on purpose: the fail-open behaviour below can only be *tested* if a
    test can break it, and it is the one behaviour nobody wants to discover in an
    incident rather than in the suite.
    """
    from app.db.session import get_sessionmaker

    return get_sessionmaker()


def rule_for(scope: str, settings: Settings | None = None) -> Rule:
    """Look a scope's allowance up in config, falling back to the generic one."""
    config = settings or get_settings()
    field = _LIMIT_FIELDS.get(scope)
    limit = getattr(config, field) if field else config.RATE_LIMIT_DEFAULT
    return Rule(
        scope=scope,
        limit=int(limit),
        window_seconds=int(config.RATE_LIMIT_WINDOW_SECONDS),
        switched_on=bool(config.RATE_LIMIT_ENABLED),
    )


def window_for(now: float, window_seconds: int) -> tuple[datetime, datetime]:
    """The aligned window containing ``now``: floor to the boundary, then add."""
    start_epoch = int(now) - (int(now) % window_seconds)
    start = datetime.fromtimestamp(start_epoch, UTC)
    return start, start + timedelta(seconds=window_seconds)


def describe_wait(seconds: int) -> str:
    """Human copy for a 429 — the customer reads this, so it says a real duration."""
    if seconds >= 120:
        minutes = (seconds + 59) // 60
        return f"{minutes} minutes"
    if seconds >= 60:
        return "1 minute"
    if seconds <= 1:
        return "1 second"
    return f"{seconds} seconds"


def caller_key(request: Request, *, prefix: str) -> str:
    """Who is calling: an authenticated user id, else a hashed client address.

    The address is hashed so the counter table is not a browsable list of who
    visited the shop. Spoofing ``X-Forwarded-For`` can buy a fresh bucket, which
    is exactly why the authenticated routes key on the user id instead — see
    docs/SECURITY.md.
    """
    host = getattr(request.client, "host", None) or "unknown"
    digest = hashlib.sha256(host.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


async def consume(scope: str, caller: str, *, settings: Settings | None = None) -> Decision | None:
    """Count one hit. Returns ``None`` when nothing was counted (disabled/failed)."""
    rule = rule_for(scope, settings)
    if not rule.enabled:
        return None

    now = time.time()
    start, end = window_for(now, rule.window_seconds)
    retry_after = max(1, int((end - datetime.fromtimestamp(now, UTC)).total_seconds()))

    try:
        sessionmaker = counter_sessionmaker()
        async with sessionmaker() as session:
            hits = await session.scalar(
                text(
                    "INSERT INTO rate_limit_counters (bucket, window_start, window_end, hits) "
                    "VALUES (:bucket, :start, :end, 1) "
                    "ON CONFLICT (bucket, window_start) DO UPDATE "
                    "SET hits = rate_limit_counters.hits + 1 "
                    "RETURNING hits"
                ),
                {"bucket": f"{scope}:{caller}", "start": start, "end": end},
            )
            await session.commit()
    except (SQLAlchemyError, RuntimeError, OSError) as exc:  # pragma: no cover - infra failure
        logger.warning("rate_limit_unavailable", scope=scope, error=type(exc).__name__)
        return None

    counted = int(hits or 1)
    if secrets.randbelow(SWEEP_ONE_IN) == 0:
        await sweep_expired()

    return Decision(
        allowed=counted <= rule.limit,
        limit=rule.limit,
        remaining=max(0, rule.limit - counted),
        retry_after_seconds=retry_after,
        window_end=end,
    )


async def enforce(scope: str, caller: str, *, settings: Settings | None = None) -> Decision | None:
    """Count one hit and raise the single 429 shape when the budget is spent."""
    decision = await consume(scope, caller, settings=settings)
    if decision is None or decision.allowed:
        return decision
    raise RateLimitedError(
        f"That's {decision.limit} in this window — please try again in "
        f"{describe_wait(decision.retry_after_seconds)}.",
        details={
            "scope": scope,
            "limit": decision.limit,
            "retry_after_seconds": decision.retry_after_seconds,
            "window_seconds": rule_for(scope, settings).window_seconds,
        },
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


async def sweep_expired() -> int:
    """Delete windows that closed more than ``SWEEP_GRACE`` ago. Returns the count."""
    cutoff = datetime.now(UTC) - SWEEP_GRACE
    try:
        sessionmaker = counter_sessionmaker()
        async with sessionmaker() as session:
            result = await session.execute(
                text("DELETE FROM rate_limit_counters WHERE window_end < :cutoff"),
                {"cutoff": cutoff},
            )
            await session.commit()
            return int(getattr(result, "rowcount", 0) or 0)
    except (SQLAlchemyError, RuntimeError, OSError) as exc:  # pragma: no cover - infra failure
        logger.warning("rate_limit_sweep_failed", error=type(exc).__name__)
        return 0


def headers_for(decision: Decision | None) -> dict[str, str]:
    """The headers a successful response carries, so a client can self-throttle."""
    if decision is None:
        return {}
    return {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Reset": str(int(decision.window_end.timestamp())),
    }
