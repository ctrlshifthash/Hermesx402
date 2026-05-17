"""Seed: a dev user with two wallets (each with budget + an agent) so the
multi-wallet UI is populated immediately.

    python -m scripts.seed

In dev auth mode the frontend authenticates as privy_did "dev:local" — this
seeds exactly that identity so the demo is populated on first load.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.db.session import Base, SessionLocal, engine
from app.models import Agent, Budget, User, Wallet

DEV_DID = "dev:local"


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.privy_did == DEV_DID))
        ).scalar_one_or_none()
        if user is None:
            user = User(privy_did=DEV_DID, email="demo@agentledger.dev")
            db.add(user)
            await db.flush()

        existing = (
            await db.execute(select(Wallet).where(Wallet.user_id == user.id))
        ).scalars().first()
        if existing:
            print("Already seeded. Dev identity:", DEV_DID)
            return

        wallets = [
            ("Treasury", "0xDEM0a11edger0000000000000000000000000001", True,
             Decimal("25")),
            ("Research Ops", "0xDEM0a11edger0000000000000000000000000002",
             False, Decimal("10")),
        ]
        for label, addr, primary, bal in wallets:
            w = Wallet(
                user_id=user.id, address=addr, network="eip155:8453",
                label=label, is_primary=primary, balance_cached=bal,
            )
            db.add(w)
            await db.flush()
            db.add(
                Budget(
                    wallet_id=w.id, daily_cap=Decimal("5"),
                    per_tx_cap=Decimal("0.50"), per_run_cap=Decimal("2"),
                )
            )
            db.add(
                Agent(
                    user_id=user.id, wallet_id=w.id,
                    name=f"{label} Scout", config_json='{"runner":"scripted"}',
                )
            )
        await db.commit()
        print("Seeded dev identity:", DEV_DID)
        print("  2 wallets (Treasury primary, Research Ops), each with an "
              "agent + budget ($0.50/tx, $2/run, $5/day)")


if __name__ == "__main__":
    asyncio.run(main())
