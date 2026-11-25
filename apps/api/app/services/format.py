"""Text formatting for notifications and email.

Money never becomes a float: ``rupees`` splits paise with ``divmod`` so the ledger
stays integral and the only thing formatted is the string a human reads.
"""

from __future__ import annotations

from datetime import date


def rupees(paise: int) -> str:
    """``64000`` → ``₹640`` · ``64050`` → ``₹640.50``."""
    whole, part = divmod(abs(paise), 100)
    grouped = f"{whole:,}"
    text = f"₹{grouped}" if part == 0 else f"₹{grouped}.{part:02d}"
    return f"-{text}" if paise < 0 else text


def day(day_value: date | None) -> str:
    """``2026-11-26`` → ``26 Nov 2026`` (the shop's own wording, not ISO)."""
    if day_value is None:
        return ""
    return f"{day_value.day} {day_value.strftime('%b')} {day_value.year}"


def items_phrase(count: int) -> str:
    return f"{count} item" if count == 1 else f"{count} items"
