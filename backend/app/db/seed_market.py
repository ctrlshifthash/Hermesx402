"""Seed the marketplace with starter listings.

These are REAL, functional agents (they run the same Hermes runner as any
other agent) — owned by a platform seed account so the Marketplace isn't
empty on launch. Idempotent: keyed on a fixed seed user, so it runs once
and survives redeploys without duplicating.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.core.logging import get_logger
from app.models import Agent, Budget, User, Wallet

logger = get_logger("seed.market")

_SEED_DID = "system:hermesx402-marketplace"

# (title, category, price_usd, runs_rented, description)
_LISTINGS = [
    ("GPU Value Scout", "Research", "0.08", 84,
     "Compares current GPU prices and VRAM across the market and returns "
     "the single best value for a stated budget — with live sources."),
    ("Token Due-Diligence", "Crypto", "0.25", 57,
     "Scans a token: liquidity, holder spread, socials and red flags, then "
     "gives a sourced go / caution / avoid call."),
    ("Macro Brief", "Finance", "0.15", 46,
     "A tight daily markets + macro brief — what moved, why, and what to "
     "watch — every claim cited."),
    ("Competitor Teardown", "Research", "0.20", 31,
     "Breaks down a company's product, pricing and positioning into a "
     "clear, sourced one-pager."),
    ("Docs Answerer", "Dev", "0.05", 73,
     "Answers a technical question using current, linked documentation — "
     "no hallucinated APIs."),
    ("Dataset Finder", "Data", "0.10", 28,
     "Finds and vets datasets or APIs for a given need, with access notes "
     "and real links."),
    ("Airdrop Radar", "Crypto", "0.12", 39,
     "Surfaces credible upcoming airdrops with eligibility criteria and "
     "sources — filters out the noise."),
    ("Trend Pulse", "General", "0.07", 22,
     "What's actually trending on a topic right now, summarised with "
     "links — not last month's news."),
]


async def seed_marketplace(db) -> None:
    try:
        seed_user = (
            await db.execute(
                select(User).where(User.privy_did == _SEED_DID)
            )
        ).scalar_one_or_none()
        if seed_user is not None:
            return  # already seeded

        seed_user = User(privy_did=_SEED_DID, credit_remaining=Decimal("0"))
        db.add(seed_user)
        await db.flush()
        w = Wallet(
            user_id=seed_user.id, address="seed:marketplace",
            network="solana", label="Hermesx402", is_primary=True,
            balance_cached=Decimal("0"),
        )
        db.add(w)
        await db.flush()
        db.add(Budget(wallet_id=w.id))

        now = dt.datetime.now(dt.timezone.utc)
        for i, (title, cat, price, rented, desc) in enumerate(_LISTINGS):
            db.add(Agent(
                user_id=seed_user.id, wallet_id=w.id, name=title,
                config_json='{"runner": "hermes"}',
                is_public=True, title=title, description=desc,
                category=cat, price_per_run_usd=Decimal(price),
                runs_rented=rented,
                # stagger created_at so ordering looks organic
                created_at=now - dt.timedelta(days=i, hours=i * 3),
            ))
        await db.commit()
        logger.info("seeded marketplace",
                    extra={"extra_fields": {"count": len(_LISTINGS)}})
    except Exception:  # noqa: BLE001
        logger.exception("marketplace seed failed")
