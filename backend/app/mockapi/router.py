"""Mock x402-gated paid API — build-stage scaffolding (spec permits).

Behaves like a real x402 resource server: paid endpoints return HTTP 402 with
the standard `accepts` envelope until an `X-PAYMENT` header is presented, then
serve data. This is a real protocol exchange (real 402, real header gate,
real retry) — only the settlement is mocked via `MockPaymentProvider`.

Path to real: delete this module and point agents at any real x402 API; the
wrapper is unchanged.
"""
from __future__ import annotations

import random

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.x402.provider import facilitator_fee_payer

router = APIRouter(prefix="/mockapi", tags=["mock-paid-api"])

_PRICE_UNITS = str(int(float(settings.mock_api_price_usdc) * 1_000_000))  # 6dp


def _payment_required() -> JSONResponse:
    extra: dict = {"name": "USDC", "decimals": 6}
    # On Solana the facilitator co-signs as fee payer + submits the tx, so
    # its pubkey must be advertised here or the SVM client can't build the
    # transaction. Discovered from the facilitator (cached).
    if (settings.x402_network or "").startswith("solana"):
        fp = facilitator_fee_payer()
        if fp:
            extra["feePayer"] = fp
    return JSONResponse(
        status_code=402,
        content={
            "x402Version": 1,
            "error": "payment required",
            "accepts": [
                {
                    "scheme": "exact",
                    "network": settings.x402_network,
                    "maxAmountRequired": _PRICE_UNITS,
                    # Required by the real x402 PaymentRequirements schema.
                    "maxTimeoutSeconds": 60,
                    "resource": "premium-data",
                    "description": "Hermesx402 premium data",
                    "mimeType": "application/json",
                    "payTo": settings.x402_pay_to
                    or "0xMockResourceServerWalletAddressFFFFFFFFFFFFFFFF",
                    "asset": settings.x402_asset_address
                    or "0xMockUSDCContractAddrFFFFFFFFFFFFFFFFFFFF",
                    "extra": extra,
                }
            ],
        },
    )


@router.get("/free/context")
async def free_context():
    return {"summary": "Baseline context: market is active; proceed.", "free": True}


@router.api_route("/paid/{topic}", methods=["GET", "POST"])
async def paid_topic(
    topic: str,
    request: Request,
    x_payment: str | None = Header(default=None),
):
    # When the real SDK resource-server middleware is active it owns the
    # 402 → verify → on-chain settle handshake; a request only reaches this
    # handler AFTER payment is verified, so just serve the data. The legacy
    # in-handler 402 stays only for mock/test/offline (no real guard).
    from app.mockapi.x402_guard import guard_active  # noqa: PLC0415

    if not guard_active() and not x_payment:
        return _payment_required()
    samples = {
        "gpu-prices": "RTX 4060 ~$299, RX 7600 ~$269, Arc A750 ~$199.",
        "gpu-benchmarks": "RTX 4060 ≈ 1.0x; RX 7600 ≈ 0.95x; A750 ≈ 0.88x.",
        "weather": "72°F, clear, wind 6mph; 7-day stable.",
        "market-quote": f"Quote {round(random.uniform(90, 110), 2)} (+1.2%).",
        "cross-check": "Independent source confirms primary findings (±3%).",
    }
    return {
        "topic": topic,
        "summary": samples.get(topic, f"Premium dataset '{topic}' delivered."),
        "paid": True,
    }
