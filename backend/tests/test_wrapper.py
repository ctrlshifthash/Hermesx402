"""x402 wrapper: 402 → budget → pay → log → retry, plus idempotency."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app.main import app
from app.models import (
    Agent, ApiCall, Budget, Payment, PaymentStatus, Run, User, Wallet,
)
from app.x402.provider import MockPaymentProvider
from app.x402.wrapper import CallContext, PaidHttpClient

pytestmark = pytest.mark.asyncio


async def _ctx(db, per_tx="0.50", per_run="2", daily="5"):
    u = User(privy_did="dev:w")
    db.add(u)
    await db.flush()
    w = Wallet(user_id=u.id, address="0xw", label="W")
    db.add(w)
    await db.flush()
    db.add(
        Budget(
            wallet_id=w.id, daily_cap=Decimal(daily),
            per_tx_cap=Decimal(per_tx), per_run_cap=Decimal(per_run),
        )
    )
    a = Agent(user_id=u.id, wallet_id=w.id, name="A", config_json="{}")
    db.add(a)
    await db.flush()
    r = Run(user_id=u.id, wallet_id=w.id, agent_id=a.id, goal="g",
            status="running")
    db.add(r)
    await db.commit()
    return CallContext(
        user_id=u.id, wallet_id=w.id, run_id=r.id, agent_id=a.id,
        purpose="test",
    )


def _client(db):
    return PaidHttpClient(
        db, MockPaymentProvider(), transport=ASGITransport(app=app)
    )


async def test_paid_flow_logs_one_payment_and_call(db):
    ctx = await _ctx(db)
    resp = await _client(db).request(
        "GET", "http://testserver/mockapi/paid/gpu-prices", ctx
    )
    assert resp.paid and resp.outcome == "ok" and resp.status_code == 200
    n_pay = (await db.execute(select(func.count()).select_from(Payment))).scalar_one()
    n_call = (await db.execute(select(func.count()).select_from(ApiCall))).scalar_one()
    assert n_pay == 1 and n_call == 1
    p = (await db.execute(select(Payment))).scalar_one()
    assert p.status == PaymentStatus.settled and p.wallet_id == ctx.wallet_id
    # Default $1 credit → trial-credit settlement: no on-chain hash,
    # tagged platform-credit (real wallet payments carry a real tx hash).
    assert p.tx_hash is None and p.facilitator_ref == "platform-credit"


async def test_free_endpoint_no_payment(db):
    ctx = await _ctx(db)
    resp = await _client(db).request(
        "GET", "http://testserver/mockapi/free/context", ctx
    )
    assert not resp.paid and resp.outcome == "ok"
    assert (await db.execute(select(func.count()).select_from(Payment))).scalar_one() == 0


async def test_over_budget_blocked_no_funds_move(db):
    ctx = await _ctx(db, per_tx="0.001")
    resp = await _client(db).request(
        "GET", "http://testserver/mockapi/paid/weather", ctx
    )
    assert resp.outcome == "blocked_budget" and not resp.paid
    settled = (
        await db.execute(
            select(func.count()).select_from(Payment).where(
                Payment.status == PaymentStatus.settled
            )
        )
    ).scalar_one()
    assert settled == 0


async def test_idempotent_no_double_pay_on_retry(db):
    ctx = await _ctx(db)
    c = _client(db)
    url = "http://testserver/mockapi/paid/cross-check"
    r1 = await c.request("GET", url, ctx)
    r2 = await c.request("GET", url, ctx)
    assert r1.paid and r2.paid
    settled = (
        await db.execute(
            select(func.count()).select_from(Payment).where(
                Payment.status == PaymentStatus.settled
            )
        )
    ).scalar_one()
    assert settled == 1
    assert r1.tx_hash == r2.tx_hash
