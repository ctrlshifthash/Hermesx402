"""Unattended scheduler: fires due recurring runs.

Runs as a background task in the API process (RUN_MODE=inproc). Every tick it
claims due schedules and launches a Run for each — same path as a manual run,
so budget/credit enforcement still applies (recurring autonomous spend is
hard-capped). For multi-process (arq) this would move to a single leader; the
fire logic is identical and documented.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import Agent, Run, RunStatus, Schedule
from app.workers.run_worker import launch_inproc

logger = get_logger("scheduler")

_TICK = 15  # seconds
_stop = False


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def _tick() -> None:
    async with SessionLocal() as db:
        due = list(
            (
                await db.execute(
                    select(Schedule).where(
                        Schedule.active.is_(True),
                        Schedule.next_run_at <= _now(),
                    )
                )
            ).scalars()
        )
        for sch in due:
            agent = (
                await db.execute(
                    select(Agent).where(Agent.id == sch.agent_id)
                )
            ).scalar_one_or_none()
            if agent is None:
                sch.active = False
                continue
            run = Run(
                user_id=sch.user_id,
                wallet_id=sch.wallet_id,
                agent_id=sch.agent_id,
                goal=sch.goal,
                status=RunStatus.queued,
            )
            db.add(run)
            await db.flush()
            sch.last_run_at = _now()
            sch.next_run_at = _now() + dt.timedelta(
                seconds=sch.interval_seconds
            )
            sch.runs_fired += 1
            await db.commit()
            launch_inproc(run.id)
            logger.info(
                "scheduled run fired",
                extra={"extra_fields": {
                    "schedule_id": sch.id, "run_id": run.id,
                }},
            )


async def scheduler_loop() -> None:
    logger.info("scheduler started", extra={"extra_fields": {"tick": _TICK}})
    while not _stop:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            logger.exception("scheduler tick failed")
        await asyncio.sleep(_TICK)
