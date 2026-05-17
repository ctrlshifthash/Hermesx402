"""Budget — per active wallet."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_wallet
from app.db.session import get_db
from app.models import Budget, Wallet
from app.schemas import BudgetIn, BudgetOut

router = APIRouter(tags=["budgets"])


async def _budget(db: AsyncSession, wallet: Wallet) -> Budget:
    b = (
        await db.execute(select(Budget).where(Budget.wallet_id == wallet.id))
    ).scalar_one_or_none()
    if b is None:
        # Self-heal: every wallet must have a budget.
        b = Budget(wallet_id=wallet.id)
        db.add(b)
        await db.commit()
        await db.refresh(b)
    return b


@router.get("/budget", response_model=BudgetOut)
async def get_budget(
    db: AsyncSession = Depends(get_db), wallet: Wallet = Depends(get_wallet)
):
    return await _budget(db, wallet)


@router.put("/budget", response_model=BudgetOut)
async def update_budget(
    body: BudgetIn,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    b = await _budget(db, wallet)
    b.daily_cap = body.daily_cap
    b.per_tx_cap = body.per_tx_cap
    b.per_run_cap = body.per_run_cap
    await db.commit()
    await db.refresh(b)
    return b
