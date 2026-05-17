"""Ops: health, metrics (R7), wallet-scoped reconciliation."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_wallet
from app.core.config import settings
from app.db.session import get_db
from app.models import Payment, PaymentStatus, Wallet
from app.services.reconcile import reconcile_wallet
from app.x402.provider import settlement_status

router = APIRouter(tags=["ops"])


@router.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "payment_provider": settings.payment_provider,
        "auth_mode": settings.auth_mode,
        # "live" = real on-chain Solana USDC settlement is armed (funded
        # signer present); "mock" = trial-credit accounting, no funds move.
        "settlement": settlement_status(),
        "pricing": {
            "run_fee_usd": settings.run_usage_fee_usd,
            "paid_call_min_usdc": settings.mock_api_price_usdc,
            "signup_credit_usd": settings.signup_credit_usd,
        },
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(db: AsyncSession = Depends(get_db)):
    out = []
    for st in PaymentStatus:
        c = (
            await db.execute(
                select(func.count())
                .select_from(Payment)
                .where(Payment.status == st)
            )
        ).scalar_one()
        out.append(f'agentledger_payments_total{{status="{st.value}"}} {c}')
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.settled
            )
        )
    ).scalar_one()
    out.append(f"agentledger_spend_usdc_total {float(total)}")
    return "\n".join(out) + "\n"


@router.post("/reconcile")
async def reconcile(
    db: AsyncSession = Depends(get_db), wallet: Wallet = Depends(get_wallet)
):
    return await reconcile_wallet(db, wallet.id)
