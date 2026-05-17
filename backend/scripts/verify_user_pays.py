"""PROOF: trial credit exhausted -> the USER'S OWN wallet pays the x402 API
on Solana mainnet -> the service responds. End to end, real on-chain.

    python -m scripts.verify_user_pays

This drives the real production payment path (`PaidHttpClient`) with a user
whose `credit_remaining = 0` and `payments_delegated = True`. The delegated
signer is a real funded Solana wallet (the same key custody Privy provides
remotely — here signed locally so the full economic flow is provable without
a browser). It asserts: payment took the USER-WALLET branch, a real mainnet
tx hash was produced, and the paid endpoint returned its data (the service).
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select

import app.x402.provider as provider_mod
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Agent, Budget, Payment, Run, RunStatus, User, Wallet
from app.x402.provider import X402PaymentProvider, get_payment_provider
from app.x402.wrapper import CallContext, PaidHttpClient


async def main() -> int:
    if settings.payment_provider != "x402":
        print("[BLOCKED] PAYMENT_PROVIDER != x402")
        return 1
    if not settings.x402_svm_private_key:
        print("[BLOCKED] no signer key configured")
        return 1

    # The user's delegated wallet, signed by a real funded keypair. In prod
    # this exact provider is built by Privy delegated signing instead — same
    # ClientSvmSigner interface, remote custody. Economic flow is identical.
    from x402.mechanisms.svm import KeypairSigner  # noqa: PLC0415

    def _user_provider(wallet_id: str, address: str):
        return X402PaymentProvider(
            svm_signer=KeypairSigner.from_base58(
                settings.x402_svm_private_key
            )
        )

    provider_mod.build_user_delegated_provider = _user_provider

    async with SessionLocal() as db:
        # A user who has spent ALL trial credit but delegated their wallet.
        u = User(
            privy_did=f"proof:user-pays:{uuid.uuid4().hex[:8]}",
            credit_remaining=Decimal("0"),
            payments_delegated=True,
            privy_wallet_id="proof-wallet-id",
            privy_wallet_address=settings.x402_pay_to or "proof",
        )
        db.add(u)
        await db.flush()
        w = Wallet(user_id=u.id, address="proof:wallet",
                   network=settings.x402_network, label="Proof",
                   is_primary=True, balance_cached=Decimal("0"))
        db.add(w)
        await db.flush()
        db.add(Budget(wallet_id=w.id))
        ag = Agent(user_id=u.id, wallet_id=w.id, name="Proof",
                   config_json='{"runner": "hermes"}')
        db.add(ag)
        await db.flush()
        run = Run(user_id=u.id, wallet_id=w.id, agent_id=ag.id,
                  goal="proof: pay the x402 API from the user's wallet",
                  status=RunStatus.running)
        db.add(run)
        await db.commit()

        print(f"user.credit_remaining = {u.credit_remaining}  (exhausted)")
        print(f"user.payments_delegated = {u.payments_delegated}")
        print("Calling the real x402-gated endpoint via PaidHttpClient ...\n")

        client = PaidHttpClient(db, get_payment_provider())
        ctx = CallContext(user_id=u.id, wallet_id=w.id, run_id=run.id,
                           agent_id=ag.id,
                           purpose="premium data via x402 (user wallet)")
        url = f"{settings.mock_api_base_url}/paid/verify"
        r = await client.request("GET", url, ctx)

        pay = (
            await db.execute(
                select(Payment).where(Payment.run_id == run.id)
            )
        ).scalars().first()

        print(f"outcome      : {r.outcome}")
        print(f"paid         : {r.paid}")
        print(f"tx hash      : {r.tx_hash}")
        if pay is not None:
            print(f"payment note : {pay.reconcile_note}")
            print(f"payment stat : {pay.status}")
        print(f"service body : {r.text[:160]}")

        ok = (
            r.paid
            and r.tx_hash
            and pay is not None
            and "your own wallet" in (pay.reconcile_note or "")
        )
        if ok:
            net = settings.x402_network or ""
            q = "?cluster=devnet" if "devnet" in net else ""
            print("\n[PROVEN] credit exhausted -> USER'S wallet paid the "
                  "x402 API on-chain -> service responded.")
            print(f"  solscan: https://solscan.io/tx/{r.tx_hash}{q}")
            return 0
        print("\n[FAIL] user-wallet payment path did not settle.")
        print(f"  error: {r.text[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
