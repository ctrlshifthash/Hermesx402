"""API calls: list (filter run/outcome/paid), get. Wallet-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_wallet
from app.db.session import get_db
from app.models import ApiCall, Wallet
from app.schemas import ApiCallOut

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("", response_model=list[ApiCallOut])
async def list_calls(
    run_id: str | None = None,
    outcome: str | None = None,
    paid: bool | None = None,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    stmt = select(ApiCall).where(ApiCall.wallet_id == wallet.id)
    if run_id:
        stmt = stmt.where(ApiCall.run_id == run_id)
    if outcome:
        stmt = stmt.where(ApiCall.outcome == outcome)
    if paid is not None:
        stmt = stmt.where(ApiCall.paid == paid)
    stmt = stmt.order_by(ApiCall.created_at.desc())
    return list((await db.execute(stmt)).scalars())


@router.get("/{call_id}", response_model=ApiCallOut)
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    c = (
        await db.execute(
            select(ApiCall).where(
                ApiCall.id == call_id, ApiCall.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "Call not found")
    return c
