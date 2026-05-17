"""Test fixtures.

Uses a temp-file SQLite DB so the API request handlers and the concurrent
in-proc run worker use independent real connections (true end-to-end, with
real transaction isolation — not a mocked seam). Schema is reset per test.
The worker's HTTP is routed to the in-process app via an ASGI transport.
"""
from __future__ import annotations

import os
import tempfile

_DB_FILE = os.path.join(tempfile.gettempdir(), "agentledger_test.db")
if os.path.exists(_DB_FILE):
    os.remove(_DB_FILE)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE}"
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["RUN_MODE"] = "inproc"
os.environ["DEBUG"] = "false"
# Force deterministic offline auth/agent regardless of a local .env.
os.environ["AUTH_MODE"] = "dev"
os.environ["PRIVY_APP_ID"] = ""
os.environ["PRIVY_VERIFICATION_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["X402_EVM_PRIVATE_KEY"] = ""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.x402.provider import set_mock_transport
from app.x402.wrapper import set_default_transport


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    # Route both the wrapper's plain request AND the mock provider's paid
    # replay to the in-process app.
    set_default_transport(ASGITransport(app=app))
    set_mock_transport(ASGITransport(app=app))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    set_default_transport(None)
    set_mock_transport(None)


@pytest_asyncio.fixture
async def db():
    async with SessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c
