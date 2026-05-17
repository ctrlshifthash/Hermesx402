"""Schedules — unattended recurring runs. Wallet-scoped; budget still applies."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_wallet
from app.db.session import get_db
from app.models import Agent, Schedule, User, Wallet
from app.schemas import ScheduleIn, ScheduleOut

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleOut])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    rows = (
        await db.execute(
            select(Schedule)
            .where(Schedule.wallet_id == wallet.id)
            .order_by(Schedule.created_at.desc())
        )
    ).scalars()
    return list(rows)


@router.post("", response_model=ScheduleOut, status_code=201)
async def create_schedule(
    body: ScheduleIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    wallet: Wallet = Depends(get_wallet),
):
    agent = (
        await db.execute(
            select(Agent).where(
                Agent.id == body.agent_id, Agent.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found on this wallet")
    sch = Schedule(
        user_id=user.id,
        wallet_id=wallet.id,
        agent_id=agent.id,
        goal=body.goal,
        interval_seconds=body.interval_seconds,
        active=True,
        next_run_at=dt.datetime.now(dt.timezone.utc)
        + dt.timedelta(seconds=body.interval_seconds),
    )
    db.add(sch)
    await db.commit()
    await db.refresh(sch)
    return sch


@router.post("/{schedule_id}/toggle", response_model=ScheduleOut)
async def toggle_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    sch = (
        await db.execute(
            select(Schedule).where(
                Schedule.id == schedule_id, Schedule.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if sch is None:
        raise HTTPException(404, "Schedule not found")
    sch.active = not sch.active
    if sch.active:
        sch.next_run_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            seconds=sch.interval_seconds
        )
    await db.commit()
    await db.refresh(sch)
    return sch


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    sch = (
        await db.execute(
            select(Schedule).where(
                Schedule.id == schedule_id, Schedule.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if sch is None:
        raise HTTPException(404, "Schedule not found")
    await db.delete(sch)
    await db.commit()
