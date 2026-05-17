"""Budget enforcement — per WALLET, checked BEFORE any payment moves funds.

Security-critical. `check_budget` returns an allow/deny decision for a proposed
spend against the wallet's caps, computed over settled+pending spend so
concurrent runs on the same wallet cannot collectively overspend.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, Payment, PaymentStatus

_COUNTED = (PaymentStatus.settled, PaymentStatus.pending)


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    cap: Decimal | None = None
    would_be: Decimal | None = None


async def _sum(
    db: AsyncSession, wallet_id: str, since: dt.datetime | None, run_id: str | None
) -> Decimal:
    stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.wallet_id == wallet_id, Payment.status.in_(_COUNTED)
    )
    if since is not None:
        stmt = stmt.where(Payment.created_at >= since)
    if run_id is not None:
        stmt = stmt.where(Payment.run_id == run_id)
    return Decimal(str((await db.execute(stmt)).scalar_one()))


async def check_budget(
    db: AsyncSession,
    *,
    wallet_id: str,
    run_id: str,
    amount: Decimal,
) -> BudgetDecision:
    budget = (
        await db.execute(select(Budget).where(Budget.wallet_id == wallet_id))
    ).scalar_one_or_none()
    if budget is None:
        return BudgetDecision(False, "no_budget_configured")
    if amount <= 0:
        return BudgetDecision(False, "non_positive_amount")

    if amount > budget.per_tx_cap:
        return BudgetDecision(False, "per_tx_cap", budget.per_tx_cap, amount)

    run_spend = await _sum(db, wallet_id, None, run_id)
    if run_spend + amount > budget.per_run_cap:
        return BudgetDecision(
            False, "per_run_cap", budget.per_run_cap, run_spend + amount
        )

    midnight = dt.datetime.now(dt.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_spend = await _sum(db, wallet_id, midnight, None)
    if day_spend + amount > budget.daily_cap:
        return BudgetDecision(
            False, "daily_cap", budget.daily_cap, day_spend + amount
        )
    return BudgetDecision(True, "")
