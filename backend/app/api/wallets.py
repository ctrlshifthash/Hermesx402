"""Wallets — a user owns many. Each gets its own budget; first is primary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Agent, Budget, User, Wallet
from app.schemas import WalletIn, WalletOut, WalletRenameIn

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("", response_model=list[WalletOut])
async def list_wallets(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(Wallet)
            .where(Wallet.user_id == user.id)
            .order_by(Wallet.is_primary.desc(), Wallet.created_at.asc())
        )
    ).scalars()
    return list(rows)


@router.post("", response_model=WalletOut, status_code=201)
async def add_wallet(
    body: WalletIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dupe = (
        await db.execute(
            select(Wallet).where(
                Wallet.user_id == user.id, Wallet.address == body.address
            )
        )
    ).scalar_one_or_none()
    if dupe:
        raise HTTPException(409, "Wallet already linked")
    count = (
        await db.execute(
            select(func.count()).select_from(Wallet).where(
                Wallet.user_id == user.id
            )
        )
    ).scalar_one()
    wallet = Wallet(
        user_id=user.id,
        address=body.address,
        network=body.network,
        label=body.label,
        is_primary=count == 0,
    )
    db.add(wallet)
    await db.flush()
    db.add(Budget(wallet_id=wallet.id))  # default caps per wallet
    db.add(  # default agent so the wallet is usable right away
        Agent(user_id=user.id, wallet_id=wallet.id,
              name="Default Agent", config_json='{"runner": "hermes"}')
    )
    await db.commit()
    await db.refresh(wallet)
    return wallet


@router.post("/{wallet_id}/rename", response_model=WalletOut)
async def rename_wallet(
    wallet_id: str,
    body: WalletRenameIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    w = (
        await db.execute(
            select(Wallet).where(
                Wallet.id == wallet_id, Wallet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if w is None:
        raise HTTPException(404, "Wallet not found")
    w.label = body.label.strip()
    await db.commit()
    await db.refresh(w)
    return w


@router.post("/{wallet_id}/primary", response_model=WalletOut)
async def set_primary(
    wallet_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list(
        (
            await db.execute(
                select(Wallet).where(Wallet.user_id == user.id)
            )
        ).scalars()
    )
    target = next((w for w in rows if w.id == wallet_id), None)
    if target is None:
        raise HTTPException(404, "Wallet not found")
    for w in rows:
        w.is_primary = w.id == wallet_id
    await db.commit()
    await db.refresh(target)
    return target


@router.delete("/{wallet_id}", status_code=204)
async def remove_wallet(
    wallet_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    w = (
        await db.execute(
            select(Wallet).where(
                Wallet.id == wallet_id, Wallet.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if w is None:
        raise HTTPException(404, "Wallet not found")
    await db.delete(w)
    await db.commit()
