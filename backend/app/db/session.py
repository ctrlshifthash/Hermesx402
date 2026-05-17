"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_is_memory = settings.is_sqlite and ":memory:" in settings.database_url
_kw: dict = {"echo": False}
if settings.is_sqlite:
    _kw["connect_args"] = {"check_same_thread": False}
    if _is_memory:
        # A bare in-memory SQLite DB is per-connection; StaticPool keeps one
        # shared connection so the API process and the in-proc worker (same
        # process) see the same data. Used by the test suite.
        _kw["poolclass"] = StaticPool
else:
    _kw["pool_pre_ping"] = True

engine = create_async_engine(settings.database_url, **_kw)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
