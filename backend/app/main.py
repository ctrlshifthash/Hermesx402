"""AgentLedger API entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agents,
    auth,
    budgets,
    calls,
    dashboard,
    marketplace,
    ops,
    payments,
    runs,
    schedules,
    wallets,
)
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import Base, engine
from app.mockapi.router import router as mock_router

configure_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # SQLite local bring-up auto-creates schema; Postgres uses Alembic
    # migrations (see alembic/). This keeps `docker-compose up` and the
    # zero-config local/e2e path both working.
    if settings.is_sqlite:
        from sqlalchemy import text  # noqa: PLC0415

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Lightweight additive migration for local SQLite (create_all
            # won't ALTER existing tables). Add columns introduced after the
            # DB file was created — idempotent, preserves existing data.
            for tbl, col, ddl in [
                ("runs", "journal", "TEXT NOT NULL DEFAULT '[]'"),
                ("users", "credit_remaining", "NUMERIC DEFAULT 1"),
                ("users", "privy_wallet_id", "VARCHAR(128)"),
                ("users", "privy_wallet_address", "VARCHAR(64)"),
                ("users", "payments_delegated",
                 "BOOLEAN NOT NULL DEFAULT 0"),
                ("agents", "is_public", "BOOLEAN NOT NULL DEFAULT 0"),
                ("agents", "title", "VARCHAR(120)"),
                ("agents", "description", "TEXT"),
                ("agents", "category", "VARCHAR(48)"),
                ("agents", "price_per_run_usd", "NUMERIC DEFAULT 0"),
                ("agents", "runs_rented", "INTEGER DEFAULT 0"),
                ("runs", "creator_user_id", "VARCHAR(36)"),
            ]:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")
                    )
                except Exception:  # noqa: BLE001
                    pass  # column already exists
    # A restart kills in-proc run tasks; their DB status would otherwise stay
    # "running"/"queued" forever (zombie runs). Fail them on boot so the UI
    # never shows a perpetually-running run.
    try:
        from sqlalchemy import update  # noqa: PLC0415

        from app.db.session import SessionLocal  # noqa: PLC0415
        from app.models import Run, RunStatus  # noqa: PLC0415

        async with SessionLocal() as _db:
            res = await _db.execute(
                update(Run)
                .where(Run.status.in_([RunStatus.queued, RunStatus.running]))
                .values(
                    status=RunStatus.failed,
                    summary="Interrupted by a server restart.",
                )
            )
            await _db.commit()
            if res.rowcount:
                logger.info(
                    "cleared orphaned runs",
                    extra={"extra_fields": {"count": res.rowcount}},
                )
    except Exception:  # noqa: BLE001
        logger.exception("orphan-run cleanup failed")

    sched_task = None
    if settings.run_mode == "inproc":
        import asyncio  # noqa: PLC0415

        from app.workers.scheduler import scheduler_loop  # noqa: PLC0415

        sched_task = asyncio.create_task(scheduler_loop())
    logger.info(
        "startup",
        extra={"extra_fields": {
            "env": settings.environment,
            "payment_provider": settings.payment_provider,
            "run_mode": settings.run_mode,
            "scheduler": sched_task is not None,
        }},
    )
    yield
    if sched_task:
        sched_task.cancel()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

import re as _re  # noqa: E402

# FRONTEND_ORIGIN may be a comma-separated list (e.g. the vercel.app URL +
# a custom domain + www) so a domain cutover never breaks CORS. Each entry
# is exact-matched (a trailing slash is tolerated/stripped); localhost/
# 127.0.0.1 on any port is always allowed for local dev.
_origins = [
    o.strip().rstrip("/")
    for o in (settings.frontend_origin or "").split(",")
    if o.strip()
]
_alt = "|".join(_re.escape(o) for o in _origins) or _re.escape(
    "https://localhost"
)

app.add_middleware(
    CORSMiddleware,
    # Header-based auth (Bearer/X-Dev-User), no cookies → credentials not
    # needed, so we can safely allow any localhost/127.0.0.1 port plus the
    # configured prod origin(s). This removes the #1 silent browser failure.
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|"
    + _alt
    + r")$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = settings.api_prefix
for r in (auth, wallets, agents, runs, schedules, payments, calls,
          budgets, dashboard, marketplace, ops):
    app.include_router(r.router, prefix=api)

# Real x402 resource-server gate (verify + on-chain settle via facilitator).
# Active only when armed for a facilitator-supported Solana network; else
# the legacy in-router 402 stays in charge (tests / offline / EVM).
from app.mockapi.x402_guard import build_payment_middleware  # noqa: E402

_pay_mw = build_payment_middleware()
if _pay_mw is not None:
    app.middleware("http")(_pay_mw)

# Mock paid API mounted at root (so its absolute URL matches MOCK_API_BASE_URL).
app.include_router(mock_router)


@app.get("/")
async def root():
    return {"service": settings.app_name, "docs": "/docs"}
