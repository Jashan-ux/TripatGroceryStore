"""Platform operations: the rate-limit counters (hardening, after Phase 5).

One table, and one deliberate choice behind it: the limiter counts in **Postgres**,
the database this shop already pays for, instead of asking the owner to sign up
for Redis and hand over another connection string. A counter is a single
`INSERT … ON CONFLICT DO UPDATE`, so two workers racing on the same bucket still
produce one row and one number.

Why a table and not memory: the API runs on Render with two workers, and a
restart wipes anything held in a process. A limit that resets whenever the
service redeploys is a limit an attacker can wait out.

Rows live for one window plus an hour of slack (``sweep_expired``), so the table
stays small on its own. Client addresses are stored hashed — the access log is
the only place a raw address appears.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RateLimitCounter(Base):
    """How many times one caller used one route inside one fixed window."""

    __tablename__ = "rate_limit_counters"
    __table_args__ = (CheckConstraint("hits >= 1", name="hits_positive"),)

    #: ``<scope>:<caller>`` — e.g. ``feedback:ip:9f2c…`` or ``orders:user:<uuid>``.
    bucket: Mapped[str] = mapped_column(String(length=120), primary_key=True)
    #: Aligned window start (UTC), so a window is the same for every worker.
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    #: When the caller's budget comes back; also what ``Retry-After`` is computed from.
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    hits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
