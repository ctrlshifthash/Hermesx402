"""arq worker (RUN_MODE=arq) for real multi-process concurrency (R9).

Start:  arq app.workers.arq_app.WorkerSettings
The job body reuses `execute_run`, so behaviour is identical to in-proc.
"""
from __future__ import annotations

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.run_worker import execute_run


async def run_job(ctx, run_id: str) -> None:
    await execute_run(run_id)


async def enqueue_run(run_id: str) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("run_job", run_id)


class WorkerSettings:
    functions = [run_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
