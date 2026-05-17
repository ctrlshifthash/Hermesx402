"""Payments: list (filterable), get, CSV export. Wallet-scoped."""
from __future__ import annotations

import csv
import io
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_wallet
from app.db.session import get_db
from app.models import Payment, Wallet
from app.schemas import PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"])


def _filtered(wallet_id: str, run_id, status, date_from, date_to):
    stmt = select(Payment).where(Payment.wallet_id == wallet_id)
    if run_id:
        stmt = stmt.where(Payment.run_id == run_id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if date_from:
        stmt = stmt.where(Payment.created_at >= dt.datetime.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(Payment.created_at <= dt.datetime.fromisoformat(date_to))
    return stmt.order_by(Payment.created_at.desc())


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    run_id: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    return list(
        (
            await db.execute(
                _filtered(wallet.id, run_id, status, date_from, date_to)
            )
        ).scalars()
    )


@router.get("/export.csv")
async def export_csv(
    run_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    rows = list(
        (await db.execute(_filtered(wallet.id, run_id, None, None, None))).scalars()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "created_at", "run_id", "amount", "currency", "network",
         "status", "tx_hash", "facilitator_ref", "reconciled"]
    )
    for p in rows:
        w.writerow([
            p.id, p.created_at, p.run_id, p.amount, p.currency, p.network,
            p.status.value, p.tx_hash or "", p.facilitator_ref or "",
            p.reconciled,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments.csv"},
    )


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    p = (
        await db.execute(
            select(Payment).where(
                Payment.id == payment_id, Payment.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Payment not found")
    return p
