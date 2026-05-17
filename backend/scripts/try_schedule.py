"""Prove the scheduler fires a due schedule into a real Run (no waiting).

    python -m scripts.try_schedule
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.db.session import Base, SessionLocal, engine
from app.models import (
    Agent, Budget, Run, Schedule, User, Wallet,
)
from app.workers.scheduler import _tick


async def main() -> None:
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        u = User(privy_did=f"dev:sch:{uuid.uuid4().hex[:8]}",
                 credit_remaining=Decimal("1"))
        db.add(u)
        await db.flush()
        w = Wallet(user_id=u.id, address="0xsch", label="S",
                   is_primary=True, balance_cached=Decimal("5"))
        db.add(w)
        await db.flush()
        db.add(Budget(wallet_id=w.id, daily_cap=Decimal("5"),
                      per_tx_cap=Decimal("0.5"), per_run_cap=Decimal("2")))
        a = Agent(user_id=u.id, wallet_id=w.id, name="Sched Bot",
                  config_json='{"runner":"scripted"}')
        db.add(a)
        await db.flush()
        # due now (next_run_at in the past)
        sch = Schedule(
            user_id=u.id, wallet_id=w.id, agent_id=a.id,
            goal="scheduled: check gpu prices",
            interval_seconds=3600, active=True,
            next_run_at=dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(seconds=5),
        )
        db.add(sch)
        await db.commit()
        sid, aid = sch.id, a.id

    runs_before = 0
    async with SessionLocal() as db:
        runs_before = (
            await db.execute(select(func.count()).select_from(Run)
                             .where(Run.agent_id == aid))
        ).scalar_one()

    await _tick()  # one scheduler tick

    async with SessionLocal() as db:
        runs_after = (
            await db.execute(select(func.count()).select_from(Run)
                             .where(Run.agent_id == aid))
        ).scalar_one()
        s = (await db.execute(
            select(Schedule).where(Schedule.id == sid))).scalar_one()
        print("runs_before:", runs_before, " runs_after:", runs_after)
        nra = s.next_run_at
        if nra.tzinfo is None:
            nra = nra.replace(tzinfo=dt.timezone.utc)
        print("schedule.runs_fired:", s.runs_fired,
              " last_run_at set:", s.last_run_at is not None,
              " next_run_at advanced:",
              nra > dt.datetime.now(dt.timezone.utc))
        ok = (runs_after == runs_before + 1 and s.runs_fired == 1
              and s.last_run_at is not None)
        print("RESULT:", "PASS — scheduler fired a real run" if ok
              else "FAIL")


if __name__ == "__main__":
    asyncio.run(main())
