"""Agent CRUD — scoped to the active wallet."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_wallet
from app.db.session import get_db
from app.models import Agent, User, Wallet
from app.schemas import AgentIn, AgentOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    rows = (
        await db.execute(
            select(Agent)
            .where(Agent.wallet_id == wallet.id)
            .order_by(Agent.created_at.desc())
        )
    ).scalars()
    return list(rows)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    wallet: Wallet = Depends(get_wallet),
):
    a = Agent(
        user_id=user.id,
        wallet_id=wallet.id,
        name=body.name,
        config_json=body.config_json,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    a = (
        await db.execute(
            select(Agent).where(
                Agent.id == agent_id, Agent.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Agent not found")
    return a


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str,
    body: AgentIn,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    a = (
        await db.execute(
            select(Agent).where(
                Agent.id == agent_id, Agent.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Agent not found")
    a.name = body.name
    a.config_json = body.config_json
    await db.commit()
    await db.refresh(a)
    return a


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    a = (
        await db.execute(
            select(Agent).where(
                Agent.id == agent_id, Agent.wallet_id == wallet.id
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Agent not found")
    await db.delete(a)
    await db.commit()
