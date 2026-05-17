"""Verify the autonomous agent: multi-tool + x402 + memory across runs.

Run 1: a task that uses the paid x402 API (fetch + pay + reason).
Run 2: SAME agent, a follow-up that should RECALL run 1 from memory.

    python -m scripts.try_llm
"""
from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.db.session import Base, SessionLocal, engine
from app.models import (
    Agent, Budget, Memory, Payment, Run, RunStatus, User, Wallet,
)
from app.services.events import hub
from app.workers.run_worker import execute_run


def safe(s) -> str:
    return str(s).encode("ascii", "replace").decode("ascii")


async def _run(db, user, wallet, agent, goal: str) -> str:
    r = Run(user_id=user.id, wallet_id=wallet.id, agent_id=agent.id,
            goal=goal, status=RunStatus.queued)
    db.add(r)
    await db.commit()
    rid = r.id
    q, _ = await hub.subscribe(rid)

    async def printer():
        while True:
            ev = await q.get()
            k, d = ev.get("kind"), ev.get("data", {})
            if k == "reasoning":
                print("  THINK:", safe(d.get("text", ""))[:170])
            elif k in ("payment_settled", "payment_blocked"):
                print(f"  $$$  {k}: {safe(d.get('amount'))} "
                      f"{safe(d.get('tx_hash'))[:24]}")
            elif k == "status":
                print("  STATUS:", safe(d))
                if d.get("status") in ("done", "failed", "stopped"):
                    return

    t = asyncio.create_task(printer())
    await execute_run(rid)
    try:
        await asyncio.wait_for(t, timeout=5)
    except asyncio.TimeoutError:
        pass
    async with SessionLocal() as d2:
        run = (await d2.execute(select(Run).where(Run.id == rid))).scalar_one()
        return run.summary or ""


async def main() -> None:
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        u = User(privy_did=f"dev:try:{uuid.uuid4().hex[:8]}",
                 credit_remaining=Decimal("1"))
        db.add(u)
        await db.flush()
        w = Wallet(user_id=u.id, address="0xtry", label="T",
                   is_primary=True, balance_cached=Decimal("25"))
        db.add(w)
        await db.flush()
        db.add(Budget(wallet_id=w.id, daily_cap=Decimal("5"),
                      per_tx_cap=Decimal("0.5"), per_run_cap=Decimal("2")))
        a = Agent(user_id=u.id, wallet_id=w.id, name="Scout",
                  config_json='{"runner":"openrouter"}')
        db.add(a)
        await db.commit()
        uid, wid, aid = u.id, w.id, a.id

    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.id == uid))).scalar_one()
        w = (await db.execute(select(Wallet).where(Wallet.id == wid))).scalar_one()
        a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one()
        print("\n===== RUN 1 (uses paid x402 API) =====")
        s1 = await _run(db, u, w, a,
                        "Use the AgentLedger premium data API to get GPU "
                        "prices and benchmarks, then recommend the best GPU "
                        "under $500. Remember your pick.")
        print("SUMMARY 1:", safe(s1)[:280])

    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.id == uid))).scalar_one()
        w = (await db.execute(select(Wallet).where(Wallet.id == wid))).scalar_one()
        a = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one()
        print("\n===== RUN 2 (same agent — should RECALL run 1) =====")
        s2 = await _run(db, u, w, a,
                        "What GPU did you recommend previously and why? "
                        "Answer from memory; do not fetch again.")
        print("SUMMARY 2:", safe(s2)[:280])

    async with SessionLocal() as db:
        mems = list((await db.execute(
            select(Memory).where(Memory.agent_id == aid))).scalars())
        pays = list((await db.execute(
            select(Payment).where(Payment.user_id == uid))).scalars())
        u = (await db.execute(select(User).where(User.id == uid))).scalar_one()
        print("\n===== RESULT =====")
        print("memories saved:", len(mems),
              "| kinds:", [m.kind for m in mems])
        print("payments settled:",
              sum(p.status.value == "settled" for p in pays),
              "| credit left:", u.credit_remaining)


if __name__ == "__main__":
    asyncio.run(main())
