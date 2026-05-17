"""Runs: create (async), get, list, stop, live WS streaming. Wallet-scoped."""
from __future__ import annotations

import asyncio
import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_wallet, rate_limiter
from app.core.config import settings
from app.core.privy import AuthError, verify_privy_token
from app.db.session import SessionLocal, get_db
from app.models import Agent, Run, RunStatus, User, Wallet
from app.schemas import RunIn, RunOut
from app.services.events import hub
from app.workers.run_worker import launch_inproc, request_stop

router = APIRouter(prefix="/runs", tags=["runs"])

_run_rl = rate_limiter(
    "run_create", settings.rate_limit_run_create, settings.rate_limit_run_window
)


@router.post("", response_model=RunOut, status_code=201)
async def create_run(
    body: RunIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    wallet: Wallet = Depends(get_wallet),
    _: None = Depends(_run_rl),
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

    # A run costs real money (LLM + web). Block it when the trial credit is
    # exhausted AND the wallet is still the auto-provisioned trial one (no
    # real funding connected) — otherwise a $0 guest could farm unlimited
    # real spend. Connecting a real wallet lifts the gate.
    from decimal import Decimal  # noqa: PLC0415

    fee = Decimal(settings.run_usage_fee_usd)
    if (
        Decimal(str(user.credit_remaining)) < fee
        and wallet.address.startswith("trial:")
    ):
        raise HTTPException(
            status_code=402,
            detail=(
                "Trial credit exhausted. Connect & fund a Solana wallet to "
                "keep running agents."
            ),
        )

    run = Run(
        user_id=user.id,
        wallet_id=wallet.id,
        agent_id=agent.id,
        goal=body.goal,
        status=RunStatus.queued,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    if settings.run_mode == "inproc":
        launch_inproc(run.id)
    else:
        from app.workers.arq_app import enqueue_run  # noqa: PLC0415

        await enqueue_run(run.id)
    return run


@router.get("", response_model=list[RunOut])
async def list_runs(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    stmt = select(Run).where(Run.wallet_id == wallet.id)
    if status:
        stmt = stmt.where(Run.status == RunStatus(status))
    stmt = stmt.order_by(Run.created_at.desc())
    return list((await db.execute(stmt)).scalars())


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    run = (
        await db.execute(
            select(Run).where(Run.id == run_id, Run.wallet_id == wallet.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@router.post("/{run_id}/sign", status_code=204)
async def submit_signature(
    run_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    """The browser returns the user's wallet signature for a paused x402
    payment (approve-at-spend). Resolves the waiting server-side signer."""
    import base64  # noqa: PLC0415

    from app.x402 import pending  # noqa: PLC0415

    run = (
        await db.execute(
            select(Run).where(Run.id == run_id, Run.wallet_id == wallet.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(404, "Run not found")
    token = body.get("token")
    if not token:
        raise HTTPException(400, "missing token")
    if body.get("error"):
        pending.resolve(token, None, error=str(body["error"])[:200])
        return
    sig_b64 = body.get("signature_b64")
    if not sig_b64:
        raise HTTPException(400, "missing signature")
    ok = pending.resolve(token, base64.b64decode(sig_b64))
    if not ok:
        raise HTTPException(409, "signature request expired or unknown")


@router.post("/{run_id}/stop", response_model=RunOut)
async def stop_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    wallet: Wallet = Depends(get_wallet),
):
    run = (
        await db.execute(
            select(Run).where(Run.id == run_id, Run.wallet_id == wallet.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(404, "Run not found")
    if run.status in (RunStatus.queued, RunStatus.running):
        request_stop(run_id)
    return run


async def _ws_user_did(websocket: WebSocket) -> str | None:
    """WS can't send headers from browsers, so identity travels as a query
    param: ?token=<privy>, ?guest=<id>, or ?dev=<id>."""
    token = websocket.query_params.get("token")
    if settings.auth_mode == "privy" and token:
        try:
            return verify_privy_token(token).did
        except AuthError:
            return None
    guest = websocket.query_params.get("guest")
    if guest:
        return f"guest:{guest}"
    if settings.auth_mode != "privy":
        dev = websocket.query_params.get("dev")
        return f"dev:{dev}" if dev else "dev:local"
    return None


@router.websocket("/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    did = await _ws_user_did(websocket)
    if did is None:
        await websocket.close(code=4401)
        return

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.privy_did == did))
        ).scalar_one_or_none()
        run = None
        if user is not None:
            run = (
                await db.execute(
                    select(Run).where(
                        Run.id == run_id, Run.user_id == user.id
                    )
                )
            ).scalar_one_or_none()
        if run is None:
            await websocket.close(code=4404)
            return
        terminal = run.status in (
            RunStatus.done, RunStatus.failed, RunStatus.stopped
        )

    queue, replay = await hub.subscribe(run_id)
    try:
        for ev in replay:
            await websocket.send_text(json.dumps(ev, default=str))
        if terminal and not replay:
            await websocket.send_text(
                json.dumps({"kind": "status", "data": {"status": "ended"}})
            )
        while True:
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_text(json.dumps(ev, default=str))
                if ev.get("kind") == "status" and ev["data"].get("status") in (
                    "done", "failed", "stopped"
                ):
                    break
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"kind": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(run_id, queue)
