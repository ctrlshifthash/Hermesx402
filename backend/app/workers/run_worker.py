"""Run execution worker.

`run_mode=inproc` (default, no Redis) executes runs as background asyncio tasks
in the API process — sufficient for local/demo and the e2e test.
`run_mode=arq` enqueues to an arq worker for real concurrency (Phase 2 R9);
the `execute_run` body is identical either way.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from app.agent.runner import get_runner
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import Agent, Run, RunStatus
from app.services.events import hub

logger = get_logger("worker")

# Cooperative stop signals for in-proc runs.
_STOP: set[str] = set()


def request_stop(run_id: str) -> None:
    _STOP.add(run_id)


async def execute_run(run_id: str) -> None:
    async with SessionLocal() as db:
        run = (
            await db.execute(select(Run).where(Run.id == run_id))
        ).scalar_one_or_none()
        if run is None or run.status != RunStatus.queued:
            return
        agent = (
            await db.execute(select(Agent).where(Agent.id == run.agent_id))
        ).scalar_one()

        run.status = RunStatus.running
        run.started_at = dt.datetime.now(dt.timezone.utc)
        await db.commit()
        await hub.publish(run_id, {"kind": "status", "data": {"status": "running"}})

        try:
            if run_id in _STOP:
                raise asyncio.CancelledError
            runner = get_runner(agent)
            # Hard ceiling: a run can never hang. 5 min is generous for the
            # web + paid-fetch + reasoning path (real ones take ~10-30s).
            summary = await asyncio.wait_for(
                runner.run(db, run, agent), timeout=300
            )
            run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one()
            if run_id in _STOP:
                run.status = RunStatus.stopped
                run.summary = "Run stopped by user."
            else:
                run.status = RunStatus.done
                run.summary = summary
        except asyncio.CancelledError:
            run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one()
            run.status = RunStatus.stopped
            run.summary = "Run stopped by user."
        except Exception as exc:  # noqa: BLE001
            run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one()
            run.status = RunStatus.failed
            run.summary = f"Run failed: {exc}"
            logger.exception("run failed")
        finally:
            run.ended_at = dt.datetime.now(dt.timezone.utc)
            await db.commit()
            _STOP.discard(run_id)
            await hub.publish(
                run_id,
                {"kind": "status", "data": {
                    "status": run.status.value, "summary": run.summary,
                    "total_spend": str(run.total_spend),
                }},
            )


def launch_inproc(run_id: str) -> None:
    asyncio.create_task(execute_run(run_id))
