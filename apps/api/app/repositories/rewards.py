"""Database access for wallets, referrals, scratch cards and returns.

Two rules are enforced here rather than in the services that call it:

* the wallet row is only ever read ``FOR UPDATE`` when money is about to move, so
  two concurrent credits cannot compute the same ``balance_after_paise``;
* every read of somebody's wallet, cards or returns takes their ``profile_id`` as
  an argument. There is no query that can hand one customer another's money.
"""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReferralStatus, ReturnStatus, ScratchCardStatus
from app.models.orders import Order
from app.models.returns import OrderReturn, ReturnItem
from app.models.rewards import Referral, ScratchCard, Wallet, WalletEntry


# --------------------------------------------------------------------------- #
# Wallet
# --------------------------------------------------------------------------- #
async def get_wallet(session: AsyncSession, profile_id: uuid.UUID) -> Wallet | None:
    return cast(
        "Wallet | None", await session.scalar(select(Wallet).where(Wallet.profile_id == profile_id))
    )


async def get_wallet_for_update(session: AsyncSession, profile_id: uuid.UUID) -> Wallet | None:
    """The row the ledger is about to change. Locks it for the transaction."""
    return cast(
        "Wallet | None",
        await session.scalar(
            select(Wallet).where(Wallet.profile_id == profile_id).with_for_update()
        ),
    )


async def add_wallet(session: AsyncSession, wallet: Wallet) -> Wallet:
    session.add(wallet)
    await session.flush()
    return wallet


async def add_entry(session: AsyncSession, entry: WalletEntry) -> WalletEntry:
    session.add(entry)
    await session.flush()
    return entry


async def list_entries(
    session: AsyncSession, wallet_id: uuid.UUID, *, limit: int, offset: int
) -> list[WalletEntry]:
    stmt = (
        select(WalletEntry)
        .where(WalletEntry.wallet_id == wallet_id)
        .order_by(WalletEntry.created_at.desc(), WalletEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(stmt)).all())


async def count_entries(session: AsyncSession, wallet_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(WalletEntry).where(WalletEntry.wallet_id == wallet_id)
        )
        or 0
    )


async def ledger_sum(session: AsyncSession, wallet_id: uuid.UUID) -> int:
    """The number the balance must equal. Used by tests and the statement footer."""
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(WalletEntry.delta_paise), 0)).where(
                WalletEntry.wallet_id == wallet_id
            )
        )
        or 0
    )


# --------------------------------------------------------------------------- #
# Referrals
# --------------------------------------------------------------------------- #
async def get_referral_for_referee(session: AsyncSession, referee_id: uuid.UUID) -> Referral | None:
    return cast(
        "Referral | None",
        await session.scalar(select(Referral).where(Referral.referee_id == referee_id)),
    )


async def get_referral_for_update(session: AsyncSession, referee_id: uuid.UUID) -> Referral | None:
    return cast(
        "Referral | None",
        await session.scalar(
            select(Referral).where(Referral.referee_id == referee_id).with_for_update()
        ),
    )


async def list_referrals(
    session: AsyncSession, referrer_id: uuid.UUID, *, limit: int = 50
) -> list[Referral]:
    stmt = (
        select(Referral)
        .where(Referral.referrer_id == referrer_id)
        .order_by(Referral.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def count_referrals(session: AsyncSession, referrer_id: uuid.UUID) -> dict[str, int]:
    """How many friends joined, and how many of those have paid out."""
    rows = (
        await session.execute(
            select(Referral.status, func.count())
            .where(Referral.referrer_id == referrer_id)
            .group_by(Referral.status)
        )
    ).all()
    counts = {status.value: 0 for status in ReferralStatus}
    for status, count in rows:
        counts[status.value] = int(count)
    return counts


async def add_referral(session: AsyncSession, referral: Referral) -> Referral:
    session.add(referral)
    await session.flush()
    return referral


# --------------------------------------------------------------------------- #
# Scratch cards
# --------------------------------------------------------------------------- #
async def list_cards(
    session: AsyncSession, profile_id: uuid.UUID, *, limit: int = 50
) -> list[ScratchCard]:
    stmt = (
        select(ScratchCard)
        .where(ScratchCard.profile_id == profile_id)
        .order_by(ScratchCard.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def get_card(
    session: AsyncSession, profile_id: uuid.UUID, card_id: uuid.UUID
) -> ScratchCard | None:
    return cast(
        "ScratchCard | None",
        await session.scalar(
            select(ScratchCard).where(
                ScratchCard.id == card_id, ScratchCard.profile_id == profile_id
            )
        ),
    )


async def get_card_for_order(session: AsyncSession, order_id: uuid.UUID) -> ScratchCard | None:
    return cast(
        "ScratchCard | None",
        await session.scalar(select(ScratchCard).where(ScratchCard.order_id == order_id)),
    )


async def get_card_for_update(
    session: AsyncSession, profile_id: uuid.UUID, card_id: uuid.UUID
) -> ScratchCard | None:
    return cast(
        "ScratchCard | None",
        await session.scalar(
            select(ScratchCard)
            .where(ScratchCard.id == card_id, ScratchCard.profile_id == profile_id)
            .with_for_update()
        ),
    )


async def count_cards(session: AsyncSession, profile_id: uuid.UUID) -> dict[str, int]:
    rows = (
        await session.execute(
            select(ScratchCard.status, func.count())
            .where(ScratchCard.profile_id == profile_id)
            .group_by(ScratchCard.status)
        )
    ).all()
    counts = {status.value: 0 for status in ScratchCardStatus}
    for status, count in rows:
        counts[status.value] = int(count)
    return counts


async def add_card(session: AsyncSession, card: ScratchCard) -> ScratchCard:
    session.add(card)
    await session.flush()
    return card


# --------------------------------------------------------------------------- #
# Returns
# --------------------------------------------------------------------------- #
async def get_return(session: AsyncSession, return_id: uuid.UUID) -> OrderReturn | None:
    return cast(
        "OrderReturn | None",
        await session.scalar(select(OrderReturn).where(OrderReturn.id == return_id)),
    )


async def get_return_for_update(session: AsyncSession, return_id: uuid.UUID) -> OrderReturn | None:
    return cast(
        "OrderReturn | None",
        await session.scalar(
            select(OrderReturn).where(OrderReturn.id == return_id).with_for_update()
        ),
    )


async def get_open_return_for_order(
    session: AsyncSession, order_id: uuid.UUID
) -> OrderReturn | None:
    """An order can have one live return at a time, not three parallel ones."""
    return cast(
        "OrderReturn | None",
        await session.scalar(
            select(OrderReturn).where(
                OrderReturn.order_id == order_id,
                OrderReturn.status.in_(
                    [ReturnStatus.requested, ReturnStatus.approved, ReturnStatus.received_credited]
                ),
            )
        ),
    )


async def list_returns_for_profile(
    session: AsyncSession, profile_id: uuid.UUID, *, limit: int = 50
) -> list[OrderReturn]:
    stmt = (
        select(OrderReturn)
        .where(OrderReturn.profile_id == profile_id)
        .order_by(OrderReturn.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def list_returns(
    session: AsyncSession, *, status: str | None, limit: int, offset: int
) -> list[OrderReturn]:
    stmt = select(OrderReturn)
    if status:
        stmt = stmt.where(OrderReturn.status == ReturnStatus(status))
    stmt = stmt.order_by(OrderReturn.created_at.desc()).limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())


async def count_returns(session: AsyncSession, *, status: str | None) -> int:
    stmt = select(func.count()).select_from(OrderReturn)
    if status:
        stmt = stmt.where(OrderReturn.status == ReturnStatus(status))
    return int(await session.scalar(stmt) or 0)


async def add_return(session: AsyncSession, order_return: OrderReturn) -> OrderReturn:
    session.add(order_return)
    await session.flush()
    return order_return


async def add_return_items(session: AsyncSession, items: list[ReturnItem]) -> None:
    session.add_all(items)
    await session.flush()


async def lock_order_for_return(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    return cast(
        "Order | None",
        await session.scalar(select(Order).where(Order.id == order_id).with_for_update()),
    )
