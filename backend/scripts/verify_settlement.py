"""Prove on-chain settlement is REAL — performs ONE real payment.

    python -m scripts.verify_settlement

Unlike `scripts.check_real` (which never moves funds), this does the real
thing once: it drives the real x402 SDK through a single $0.01 USDC payment
on the configured network and prints the on-chain transaction hash + a block
explorer link you can open and verify.

It WILL move a tiny amount of real USDC (and a little SOL for fees) FROM the
platform signer (X402_SVM_PRIVATE_KEY) TO X402_PAY_TO. Run it only when you
have funded that signer and you want proof the pipeline is genuinely live.

Requires the API running locally (it pays the app's own x402-gated endpoint):
    uvicorn app.main:app --port 8000
"""
from __future__ import annotations

import sys

import httpx

from app.core.config import settings
from app.x402.provider import settlement_status


def main() -> int:
    print(f"payment_provider = {settings.payment_provider}")
    print(f"network          = {settings.x402_network}")
    print(f"pay_to           = {settings.x402_pay_to}\n")

    st = settlement_status()
    if st.get("mode") != "live":
        print("[BLOCKED] Real settlement is NOT armed.")
        print(f"          reason: {st.get('reason')}")
        print(
            "\nTo arm it: put a funded base58 Solana secret key in "
            "backend/.env\n  X402_SVM_PRIVATE_KEY=...\n"
            "The signer needs a little SOL (fees) + USDC. Nothing was sent."
        )
        return 1

    print(f"[ARMED] signer {st.get('signer')}  ->  pay_to {st.get('pay_to')}")
    url = f"{settings.mock_api_base_url}/paid/verify"
    print(f"Paying the x402-gated endpoint: {url}\n")

    from decimal import Decimal

    from app.x402.provider import PaymentRequired, X402PaymentProvider

    try:
        ping = httpx.get(url, timeout=15)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] API not reachable at {url} — is uvicorn running? ({exc})")
        return 1
    if ping.status_code != 402:
        print(f"[FAIL] expected a 402 gate, got {ping.status_code}: "
              f"{ping.text[:200]}")
        return 1
    print("402 gate present — letting the real x402 client negotiate + settle")

    # The real x402 SDK client performs the full 402 → pay → settle exchange
    # internally; `terms` is unused on that path, so a stub is fine here.
    terms = PaymentRequired(
        amount=Decimal(settings.mock_api_price_usdc),
        currency="USDC", network=settings.x402_network,
        pay_to=settings.x402_pay_to or "", raw={},
    )
    provider = X402PaymentProvider()

    import asyncio

    result = asyncio.run(
        provider.pay_and_fetch(
            "GET", url, json=None, headers={},
            terms=terms, idempotency_key="verify_settlement_oneshot",
        )
    )

    if result.success and result.tx_hash:
        tx = result.tx_hash
        devnet = "devnet" in (settings.x402_network or "")
        q = "?cluster=devnet" if devnet else ""
        print("\n[REAL SETTLEMENT OK] funds moved on-chain"
              + (" (devnet test USDC)" if devnet else "") + ".")
        print(f"  tx hash : {tx}")
        print(f"  solscan : https://solscan.io/tx/{tx}{q}")
        print(f"  explorer: https://explorer.solana.com/tx/{tx}{q}")
        return 0

    print("\n[FAIL] no on-chain settlement recorded.")
    print(f"  status : {result.status_code}")
    print(f"  error  : {result.error}")
    print("  (No tx hash returned by the facilitator — funds likely NOT moved.)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
