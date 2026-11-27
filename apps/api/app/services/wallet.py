"""The wallet: one balance, one append-only ledger, integer paise.

Every mutation goes through :func:`credit` or :func:`debit`, which lock the wallet
row, write the entry and move the balance in the same transaction. Nothing else is
allowed to touch ``balance_paise`` — that is what keeps "the ledger adds up" a fact
rather than a hope, and it is asserted in ``tests/test_wallet.py``.

The wallet is created lazily, on first read or first credit, so a customer who has
never earned anything has no row to keep in step.
"""

from __future__ import annotations

import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.models.catalogue import Profile
from app.models.enums import WalletReason
from app.models.rewards import Wallet, WalletEntry
from app.repositories import rewards as repo
from app.schemas.rewards import WalletEntryOut, WalletOut

logger = get_logger(__name__)


async def _wallet(session: AsyncSession, profile_id: uuid.UUID, *, lock: bool) -> Wallet:
    """The customer's wallet row, created on demand (and locked when money moves)."""
    wallet = (
        await repo.get_wallet_for_update(session, profile_id)
        if lock
        else await repo.get_wallet(session, profile_id)
    )
    if wallet is not None:
        return wallet
    wallet = Wallet(profile_id=profile_id, balance_paise=0)
    await repo.add_wallet(session, wallet)
    if lock:
        # Re-read under the lock: a concurrent insert would have failed the unique
        # constraint, and this row is the one we now own for the transaction.
        locked = await repo.get_wallet_for_update(session, profile_id)
        return locked if locked is not None else wallet
    return wallet


async def balance(session: AsyncSession, profile_id: uuid.UUID) -> int:
    wallet = await repo.get_wallet(session, profile_id)
    return wallet.balance_paise if wallet else 0


async def credit(
    session: AsyncSession,
    profile_id: uuid.UUID,
    amount_paise: int,
    reason: WalletReason,
    *,
    note: str = "",
    order_id: uuid.UUID | None = None,
    return_id: uuid.UUID | None = None,
    scratch_card_id: uuid.UUID | None = None,
) -> WalletEntry:
    """Add money. Refuses nonsense amounts rather than silently ignoring them."""
    if amount_paise <= 0:
        raise ConflictError(
            "A wallet credit has to be more than nothing.", code="wallet_credit_invalid"
        )
    wallet = await _wallet(session, profile_id, lock=True)
    wallet.balance_paise += amount_paise
    entry = WalletEntry(
        wallet_id=wallet.id,
        delta_paise=amount_paise,
        balance_after_paise=wallet.balance_paise,
        reason=reason,
        order_id=order_id,
        return_id=return_id,
        scratch_card_id=scratch_card_id,
        note=note,
    )
    await repo.add_entry(session, entry)
    logger.info(
        "wallet_credit",
        profile_id=str(profile_id),
        amount_paise=amount_paise,
        reason=reason.value,
        balance_paise=wallet.balance_paise,
    )
    return entry


async def debit(
    session: AsyncSession,
    profile_id: uuid.UUID,
    amount_paise: int,
    reason: WalletReason,
    *,
    note: str = "",
    order_id: uuid.UUID | None = None,
) -> WalletEntry:
    """Take money out. Insufficient balance is a conflict, never a negative wallet."""
    if amount_paise <= 0:
        raise ConflictError(
            "A wallet payment has to be more than nothing.", code="wallet_debit_invalid"
        )
    wallet = await _wallet(session, profile_id, lock=True)
    if wallet.balance_paise < amount_paise:
        raise ConflictError(
            "Your wallet does not have that much in it.",
            code="wallet_insufficient",
            details={"balance_paise": wallet.balance_paise, "requested_paise": amount_paise},
        )
    wallet.balance_paise -= amount_paise
    entry = WalletEntry(
        wallet_id=wallet.id,
        delta_paise=-amount_paise,
        balance_after_paise=wallet.balance_paise,
        reason=reason,
        order_id=order_id,
        note=note,
    )
    await repo.add_entry(session, entry)
    logger.info(
        "wallet_debit",
        profile_id=str(profile_id),
        amount_paise=amount_paise,
        reason=reason.value,
        balance_paise=wallet.balance_paise,
    )
    return entry


async def statement(
    session: AsyncSession, profile: Profile, *, page: int, page_size: int
) -> WalletOut:
    wallet = await repo.get_wallet(session, profile.id)
    if wallet is None:
        return WalletOut(
            balance_paise=0,
            entries=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )
    rows = await repo.list_entries(
        session, wallet.id, limit=page_size, offset=(page - 1) * page_size
    )
    total = await repo.count_entries(session, wallet.id)
    return WalletOut(
        balance_paise=wallet.balance_paise,
        entries=[WalletEntryOut.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
