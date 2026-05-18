"""Agent marketplace — browse + rent published agents; creator earnings.

Publishing is on /agents/{id}/publish. Renting happens via the normal run
flow (create_run accepts a public agent you don't own); the payment split
records a creator-fee Payment tagged facilitator_ref='creator-earning'.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Agent, Payment, User
from app.schemas import EarningsOut, MarketplaceItem

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

CREATOR_TAG = "creator-earning"


@router.get("", response_model=list[MarketplaceItem])
async def list_marketplace(
    q: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Agent).where(Agent.is_public.is_(True))
    if category and category != "All":
        stmt = stmt.where(Agent.category == category)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Agent.title).like(like)
            | func.lower(Agent.description).like(like)
        )
    stmt = stmt.order_by(Agent.runs_rented.desc(), Agent.created_at.desc())
    return list((await db.execute(stmt)).scalars())


@router.get("/earnings", response_model=EarningsOut)
async def my_earnings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """What this user has earned from others renting their agents."""
    rows = list(
        (
            await db.execute(
                select(Payment).where(
                    Payment.user_id == user.id,
                    Payment.facilitator_ref == CREATOR_TAG,
                )
            )
        ).scalars()
    )
    total = sum((Decimal(str(p.amount)) for p in rows), Decimal("0"))
    by_agent: dict[str, dict] = {}
    for p in rows:
        note = p.reconcile_note or "agent"
        slot = by_agent.setdefault(note, {"name": note, "amount": Decimal("0"),
                                          "count": 0})
        slot["amount"] += Decimal(str(p.amount))
        slot["count"] += 1
    return EarningsOut(
        total_earned_usd=total,
        rented_runs=len(rows),
        by_agent=[
            {"name": v["name"], "amount": str(v["amount"]),
             "count": v["count"]}
            for v in by_agent.values()
        ],
    )


@router.get("/{agent_id}", response_model=MarketplaceItem)
async def marketplace_detail(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    a = (
        await db.execute(
            select(Agent).where(
                Agent.id == agent_id, Agent.is_public.is_(True)
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Listing not found")
    return a
