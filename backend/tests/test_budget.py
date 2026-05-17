"""Budget enforcement (per wallet) — the security-critical path."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models import Budget, Payment, PaymentStatus, User, Wallet
from app.services.budget import check_budget

pytestmark = pytest.mark.asyncio


async def _wallet(db, per_tx="0.25", per_run="0.50", daily="1.00"):
    u = User(privy_did="dev:b")
    db.add(u)
    await db.flush()
    w = Wallet(user_id=u.id, address="0xw1", label="W")
    db.add(w)
    await db.flush()
    db.add(
        Budget(
            wallet_id=w.id,
            daily_cap=Decimal(daily),
            per_tx_cap=Decimal(per_tx),
            per_run_cap=Decimal(per_run),
        )
    )
    await db.commit()
    return u, w


def _pay(w, u, amt, run, key, status=PaymentStatus.settled):
    return Payment(
        api_call_id="c", run_id=run, wallet_id=w.id, user_id=u.id,
        amount=Decimal(amt), currency="USDC", network="n",
        status=status, idempotency_key=key,
    )


async def test_allows_within_all_caps(db):
    u, w = await _wallet(db)
    d = await check_budget(db, wallet_id=w.id, run_id="r1", amount=Decimal("0.10"))
    assert d.allowed


async def test_blocks_over_per_tx(db):
    u, w = await _wallet(db)
    d = await check_budget(db, wallet_id=w.id, run_id="r1", amount=Decimal("0.30"))
    assert not d.allowed and d.reason == "per_tx_cap"


async def test_blocks_over_per_run(db):
    u, w = await _wallet(db)
    for i in range(2):
        db.add(_pay(w, u, "0.20", "r1", f"k{i}"))
    await db.commit()
    d = await check_budget(db, wallet_id=w.id, run_id="r1", amount=Decimal("0.20"))
    assert not d.allowed and d.reason == "per_run_cap"


async def test_blocks_over_daily(db):
    u, w = await _wallet(db)
    for i in range(4):
        db.add(_pay(w, u, "0.24", f"r{i}", f"d{i}"))
    await db.commit()
    d = await check_budget(db, wallet_id=w.id, run_id="rZ", amount=Decimal("0.10"))
    assert not d.allowed and d.reason == "daily_cap"


async def test_pending_counts_against_caps(db):
    u, w = await _wallet(db)
    db.add(_pay(w, u, "0.40", "r1", "p1", PaymentStatus.pending))
    await db.commit()
    d = await check_budget(db, wallet_id=w.id, run_id="r1", amount=Decimal("0.20"))
    assert not d.allowed and d.reason == "per_run_cap"


async def test_blocked_payment_does_not_count(db):
    u, w = await _wallet(db)
    db.add(_pay(w, u, "5", "r1", "x1", PaymentStatus.blocked_budget))
    await db.commit()
    d = await check_budget(db, wallet_id=w.id, run_id="r1", amount=Decimal("0.10"))
    assert d.allowed
