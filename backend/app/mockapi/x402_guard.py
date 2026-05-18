"""Real x402 resource-server gate (the missing piece for live settlement).

Our hand-rolled 402 only checked that an X-PAYMENT header was *present* — it
never asked the facilitator to verify + settle, so no funds ever moved. The
official x402 SDK FastAPI middleware does the real server side: returns a
proper 402, verifies the client's payment, calls the facilitator to settle
it on-chain, and sets the settlement response header (the real tx hash).

Only active when PAYMENT_PROVIDER=x402 on a Solana network whose settlement
the configured facilitator actually supports. Otherwise None → the legacy
mock 402 path in router.py stays in charge (tests, offline, EVM).
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("x402.guard")


def guard_active() -> bool:
    """True when the real SDK resource-server middleware owns the x402
    handshake — in which case the legacy in-router 402 must stand down so
    there is exactly ONE 402 implementation (no v1/v2 collision)."""
    net = (settings.x402_network or "").lower()
    return (
        settings.payment_provider == "x402"
        and net.startswith("solana")
        and bool(settings.x402_pay_to)
    )


def build_payment_middleware():
    if not guard_active():
        return None
    net = (settings.x402_network or "").lower()
    try:
        from x402 import x402ResourceServer  # noqa: PLC0415
        from x402.http import HTTPFacilitatorClient  # noqa: PLC0415
        from x402.http.middleware.fastapi import (  # noqa: PLC0415
            payment_middleware,
        )
        from x402.mechanisms.svm.constants import (  # noqa: PLC0415
            V1_TO_V2_NETWORK_MAP,
        )
        from x402.mechanisms.svm.exact.register import (  # noqa: PLC0415
            register_exact_svm_server,
        )

        facilitator = HTTPFacilitatorClient(
            {"url": settings.x402_facilitator_url}
        )
        server = x402ResourceServer(facilitator)
        register_exact_svm_server(server)

        caip = V1_TO_V2_NETWORK_MAP.get(net, net)
        accepts = {
            "scheme": "exact",
            "pay_to": settings.x402_pay_to,
            "price": f"${settings.mock_api_price_usdc}",
            "network": caip,
            "max_timeout_seconds": 60,
        }

        async def _rent_price(context) -> str:  # noqa: ANN001
            """Dynamic price = the rented agent's listing price (USD).
            Path is /mockapi/rent/<run_id>."""
            try:
                rid = context.path.rstrip("/").split("/")[-1]
                from sqlalchemy import select  # noqa: PLC0415

                from app.db.session import SessionLocal  # noqa: PLC0415
                from app.models import Agent, Run  # noqa: PLC0415

                async with SessionLocal() as db:
                    run = (
                        await db.execute(
                            select(Run).where(Run.id == rid)
                        )
                    ).scalar_one_or_none()
                    if run is None:
                        return "$0"
                    ag = (
                        await db.execute(
                            select(Agent).where(Agent.id == run.agent_id)
                        )
                    ).scalar_one_or_none()
                    price = float(ag.price_per_run_usd or 0) if ag else 0.0
                return f"${max(price, 0.0):.6f}"
            except Exception:  # noqa: BLE001
                return "$0"

        rent_accepts = {
            "scheme": "exact",
            "pay_to": settings.x402_pay_to,
            "price": _rent_price,
            "network": caip,
            "max_timeout_seconds": 90,
        }
        routes = {
            "GET /mockapi/paid/*": {"accepts": [accepts]},
            "POST /mockapi/paid/*": {"accepts": [accepts]},
            "GET /mockapi/rent/*": {"accepts": [rent_accepts]},
            "POST /mockapi/rent/*": {"accepts": [rent_accepts]},
        }
        logger.info(
            "x402 resource-server guard active",
            extra={"extra_fields": {"network": caip,
                                    "facilitator": settings.x402_facilitator_url}},
        )
        return payment_middleware(routes, server)
    except Exception:  # noqa: BLE001
        logger.exception("x402 guard build failed; falling back to legacy 402")
        return None
