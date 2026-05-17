"""Dashboard aggregates — computed for the active wallet."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_wallet
from app.db.session import get_db
from app.models import Agent, ApiCall, Payment, PaymentStatus, Run, Wallet
from app.schemas import DashboardOut, NamedAmount, RunOut, SpendPoint

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _host(url: str) -> str:
    try:
        return url.split("/")[2]
    except IndexError:
        return url


@router.get("", response_model=DashboardOut)
async def dashboard(
    db: AsyncSession = Depends(get_db), wallet: Wallet = Depends(get_wallet)
):
    wid = wallet.id
    settled = (Payment.wallet_id == wid, Payment.status == PaymentStatus.settled)

    total_spend = Decimal(
        str(
            (
                await db.execute(
                    select(func.coalesce(func.sum(Payment.amount), 0)).where(*settled)
                )
            ).scalar_one()
        )
    )
    total_runs = (
        await db.execute(
            select(func.count()).select_from(Run).where(Run.wallet_id == wid)
        )
    ).scalar_one()
    total_calls = (
        await db.execute(
            select(func.count()).select_from(ApiCall).where(ApiCall.wallet_id == wid)
        )
    ).scalar_one()
    blocked = (
        await db.execute(
            select(func.count())
            .select_from(ApiCall)
            .where(ApiCall.wallet_id == wid, ApiCall.outcome == "blocked_budget")
        )
    ).scalar_one()
    ok = (
        await db.execute(
            select(func.count())
            .select_from(ApiCall)
            .where(ApiCall.wallet_id == wid, ApiCall.outcome == "ok")
        )
    ).scalar_one()
    success_rate = round(ok / total_calls, 4) if total_calls else 0.0

    rows = (
        await db.execute(
            select(func.date(Payment.created_at), func.sum(Payment.amount))
            .where(*settled)
            .group_by(func.date(Payment.created_at))
            .order_by(func.date(Payment.created_at))
        )
    ).all()
    spend_over_time = [
        SpendPoint(bucket=str(b), amount=Decimal(str(a or 0))) for b, a in rows
    ]

    api_rows = (
        await db.execute(
            select(ApiCall.url, func.sum(Payment.amount), func.count(Payment.id))
            .join(Payment, Payment.api_call_id == ApiCall.id)
            .where(Payment.wallet_id == wid, Payment.status == PaymentStatus.settled)
            .group_by(ApiCall.url)
        )
    ).all()
    by_api: dict[str, list] = {}
    for url, amt, cnt in api_rows:
        h = _host(url)
        agg = by_api.setdefault(h, [Decimal("0"), 0])
        agg[0] += Decimal(str(amt or 0))
        agg[1] += cnt
    spend_by_api = sorted(
        [NamedAmount(name=k, amount=v[0], count=v[1]) for k, v in by_api.items()],
        key=lambda x: x.amount,
        reverse=True,
    )

    agent_rows = (
        await db.execute(
            select(Agent.name, func.sum(Payment.amount), func.count(Payment.id))
            .join(Run, Run.agent_id == Agent.id)
            .join(Payment, Payment.run_id == Run.id)
            .where(Payment.wallet_id == wid, Payment.status == PaymentStatus.settled)
            .group_by(Agent.name)
        )
    ).all()
    spend_by_agent = [
        NamedAmount(name=n, amount=Decimal(str(a or 0)), count=c)
        for n, a, c in agent_rows
    ]

    recent = list(
        (
            await db.execute(
                select(Run)
                .where(Run.wallet_id == wid)
                .order_by(Run.created_at.desc())
                .limit(5)
            )
        ).scalars()
    )

    return DashboardOut(
        total_spend=total_spend,
        total_runs=total_runs,
        total_calls=total_calls,
        blocked_calls=blocked,
        success_rate=success_rate,
        spend_over_time=spend_over_time,
        spend_by_api=spend_by_api,
        spend_by_agent=spend_by_agent,
        top_apis_paid=spend_by_api[:5],
        recent_runs=[RunOut.model_validate(r) for r in recent],
    )
