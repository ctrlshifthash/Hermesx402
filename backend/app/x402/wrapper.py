"""The x402 wrapper — the heart of the product.

Every outbound HTTP request an agent makes goes through `PaidHttpClient.request`.
Contract (spec §3), implemented fully and provider-agnostic:

1. Accept request + context (run_id, agent_id, user_id, intent/purpose).
2. Make a plain request; on 402 parse payment terms.
3. BEFORE paying: enforce budget (per-tx / per-run / daily). If exceeded:
   block, persist outcome="blocked_budget", emit event, return — NO funds move.
   (For the real provider this matters: the x402 SDK auto-pays internally, so
   it is only ever invoked AFTER this gate passes.)
4. Claim a unique payment row on a deterministic idempotency key, then call
   the provider's `pay_and_fetch` exactly once. A retry or mid-flight crash
   reuses the row instead of paying again.
5. The provider pays + fetches; we capture tx hash / facilitator ref.
6. Persist exactly ONE api_call row and (when paid) ONE payment row.
7. Emit a realtime event on the run's WebSocket channel.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ApiCall, Payment, PaymentStatus, Run, User
from app.services.budget import check_budget
from app.services.events import hub
from app.x402.provider import PaymentProvider, PaymentRequired

logger = get_logger("x402.wrapper")

# Production leaves this None → real network transport. The test suite sets it
# to an ASGITransport so the in-proc worker reaches the in-process mock API
# (the worker bypasses FastAPI DI, so this is the injection point).
_DEFAULT_TRANSPORT: httpx.AsyncBaseTransport | None = None


def set_default_transport(t: httpx.AsyncBaseTransport | None) -> None:
    global _DEFAULT_TRANSPORT
    _DEFAULT_TRANSPORT = t


@dataclass
class CallContext:
    user_id: str
    wallet_id: str
    run_id: str
    agent_id: str
    purpose: str  # human-readable intent, surfaced in the UI


@dataclass
class PaidResponse:
    status_code: int
    text: str
    paid: bool
    outcome: str  # ok | blocked_budget | error | unpaid
    amount: Decimal | None
    tx_hash: str | None
    api_call_id: str


def _idempotency_key(ctx: CallContext, method: str, url: str) -> str:
    basis = f"{ctx.run_id}|{ctx.agent_id}|{method.upper()}|{url}|{ctx.purpose}"
    return "ik_" + hashlib.sha256(basis.encode()).hexdigest()[:48]


class PaidHttpClient:
    def __init__(
        self,
        db: AsyncSession,
        provider: PaymentProvider,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.db = db
        self.provider = provider
        self._transport = transport if transport is not None else _DEFAULT_TRANSPORT

    async def _emit(self, run_id: str, kind: str, **data) -> None:
        await hub.publish(run_id, {"kind": kind, "ts": time.time(), "data": data})

    async def request(
        self,
        method: str,
        url: str,
        ctx: CallContext,
        *,
        json: dict | None = None,
        headers: dict | None = None,
        timeout: float = 30.0,
    ) -> PaidResponse:
        started = time.perf_counter()
        call = ApiCall(
            run_id=ctx.run_id,
            wallet_id=ctx.wallet_id,
            agent_id=ctx.agent_id,
            user_id=ctx.user_id,
            url=url,
            method=method.upper(),
            purpose=ctx.purpose,
            outcome="unpaid",
        )
        self.db.add(call)
        await self.db.flush()
        await self._emit(
            ctx.run_id, "api_call_started",
            api_call_id=call.id, url=url, purpose=ctx.purpose,
        )

        try:
            client_kw: dict = {"timeout": timeout}
            if self._transport is not None:
                client_kw["transport"] = self._transport
            async with httpx.AsyncClient(**client_kw) as http:
                resp = await http.request(
                    method, url, json=json, headers=headers or {}
                )

                if resp.status_code != 402:
                    return await self._finalize_unpaid(call, ctx, resp, started)

                terms = self.provider.parse_402(resp)
                await self._emit(
                    ctx.run_id, "payment_required",
                    api_call_id=call.id, amount=str(terms.amount),
                    currency=terms.currency,
                )

                decision = await check_budget(
                    self.db, wallet_id=ctx.wallet_id,
                    run_id=ctx.run_id, amount=terms.amount,
                )
                if not decision.allowed:
                    return await self._blocked(call, ctx, terms, decision, started)

                return await self._pay(
                    call, ctx, terms, method, url, json, headers or {}, started
                )

        except httpx.HTTPError as exc:
            call.outcome = "error"
            call.latency_ms = int((time.perf_counter() - started) * 1000)
            await self._commit()
            logger.warning(
                "http error",
                extra={"extra_fields": {"url": url, "err": str(exc)}},
            )
            await self._emit(
                ctx.run_id, "api_call_error", api_call_id=call.id, error=str(exc)
            )
            return PaidResponse(0, str(exc), False, "error", None, None, call.id)

    # --- helpers -------------------------------------------------------

    async def _finalize_unpaid(self, call, ctx, resp, started) -> PaidResponse:
        call.status_code = resp.status_code
        call.outcome = "ok" if resp.is_success else "error"
        call.latency_ms = int((time.perf_counter() - started) * 1000)
        await self._update_run_totals(ctx.run_id, Decimal("0"))
        await self._commit()
        await self._emit(
            ctx.run_id, "api_call_done",
            api_call_id=call.id, status=resp.status_code, paid=False,
        )
        return PaidResponse(
            resp.status_code, resp.text, False, call.outcome, None, None, call.id
        )

    async def _blocked(self, call, ctx, terms, decision, started) -> PaidResponse:
        # Funds do NOT move. The provider is never invoked.
        call.status_code = 402
        call.outcome = "blocked_budget"
        call.paid = False
        call.latency_ms = int((time.perf_counter() - started) * 1000)
        self.db.add(
            Payment(
                api_call_id=call.id, run_id=ctx.run_id, user_id=ctx.user_id,
                wallet_id=ctx.wallet_id,
                amount=terms.amount, currency=terms.currency,
                network=terms.network, status=PaymentStatus.blocked_budget,
                idempotency_key=_idempotency_key(ctx, call.method, call.url)
                + "_blk",
                reconcile_note=f"blocked: {decision.reason}",
            )
        )
        await self._commit()
        await self._emit(
            ctx.run_id, "payment_blocked",
            api_call_id=call.id, amount=str(terms.amount),
            reason=decision.reason, cap=str(decision.cap),
        )
        logger.info(
            "payment blocked by budget",
            extra={"extra_fields": {
                "user_id": ctx.user_id, "run_id": ctx.run_id,
                "reason": decision.reason, "amount": str(terms.amount),
            }},
        )
        return PaidResponse(
            402, "blocked by budget", False, "blocked_budget",
            terms.amount, None, call.id,
        )

    async def _pay(
        self, call, ctx, terms, method, url, json, headers, started
    ) -> PaidResponse:
        """Idempotently claim a payment row, pay exactly once, persist."""
        key = _idempotency_key(ctx, method, url)
        existing = (
            await self.db.execute(
                select(Payment).where(Payment.idempotency_key == key)
            )
        ).scalar_one_or_none()

        if existing is not None and existing.status in (
            PaymentStatus.settled, PaymentStatus.pending
        ):
            # Already paid (or a prior attempt is in flight). Never re-pay.
            if existing.status == PaymentStatus.pending:
                existing.reconcile_note = (
                    "pending on retry — possible mid-settle crash; "
                    "reconciler must verify before any re-pay"
                )
                await self._commit()
            call.status_code = 402
            call.paid = existing.status == PaymentStatus.settled
            call.outcome = "ok" if call.paid else "error"
            call.latency_ms = int((time.perf_counter() - started) * 1000)
            await self._commit()
            return PaidResponse(
                402, "idempotent: reused prior payment",
                call.paid, call.outcome, terms.amount,
                existing.tx_hash, call.id,
            )

        # --- Who pays? Platform trial credit first, then the user's own
        # wallet. (Per-user wallet signing via Privy delegation is the next
        # layer; until then, no credit = blocked, funds never move.)
        user = (
            await self.db.execute(
                select(User).where(User.id == ctx.user_id)
            )
        ).scalar_one()
        from_credit = Decimal(str(user.credit_remaining)) >= terms.amount

        # Trial credit exhausted → pay from the USER'S OWN wallet. Either:
        #  (a) they delegated signing (Privy) → server asks Privy to sign, or
        #  (b) default: the run pauses and the user approves the payment in
        #      their own browser wallet at spend time.
        # The server never holds their key in either case.
        user_provider = None
        if not from_credit:
            if (
                user.payments_delegated
                and user.privy_wallet_id
                and user.privy_wallet_address
            ):
                from app.x402.provider import (  # noqa: PLC0415
                    build_user_delegated_provider,
                )

                try:
                    user_provider = build_user_delegated_provider(
                        user.privy_wallet_id, user.privy_wallet_address
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("delegated provider init failed: %s", exc)

            if user_provider is None:
                # Approve-at-spend: need the user's real connected wallet
                # address (not the auto-provisioned trial container).
                import asyncio as _asyncio  # noqa: PLC0415

                from app.models import Wallet as _W  # noqa: PLC0415

                addr = user.privy_wallet_address
                if not addr:
                    rows = list(
                        (
                            await self.db.execute(
                                select(_W).where(_W.user_id == ctx.user_id)
                            )
                        ).scalars()
                    )
                    real = next(
                        (w.address for w in rows
                         if not w.address.startswith("trial:")),
                        None,
                    )
                    addr = real
                if addr:
                    from app.x402.provider import (  # noqa: PLC0415
                        build_browser_signed_provider,
                    )

                    try:
                        user_provider = build_browser_signed_provider(
                            ctx.run_id, addr,
                            _asyncio.get_running_loop(),
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("browser signer init failed: %s", exc)

            if user_provider is None:
                call.status_code = 402
                call.outcome = "credit_exhausted"
                call.paid = False
                call.latency_ms = int(
                    (time.perf_counter() - started) * 1000
                )
                self.db.add(
                    Payment(
                        api_call_id=call.id, run_id=ctx.run_id,
                        user_id=ctx.user_id, wallet_id=ctx.wallet_id,
                        amount=terms.amount, currency=terms.currency,
                        network=terms.network,
                        status=PaymentStatus.failed,
                        idempotency_key=key + "_nocredit",
                        reconcile_note="trial credit exhausted — connect a "
                        "wallet and enable agent payments to continue",
                    )
                )
                await self._commit()
                await self._emit(
                    ctx.run_id, "payment_blocked",
                    api_call_id=call.id, amount=str(terms.amount),
                    reason="credit_exhausted",
                    cap=str(user.credit_remaining),
                )
                return PaidResponse(
                    402, "trial credit exhausted", False,
                    "credit_exhausted", terms.amount, None, call.id,
                )

        payment = Payment(
            api_call_id=call.id, run_id=ctx.run_id, user_id=ctx.user_id,
            wallet_id=ctx.wallet_id,
            amount=terms.amount, currency=terms.currency,
            network=terms.network, status=PaymentStatus.pending,
            idempotency_key=key,
        )
        self.db.add(payment)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            payment = (
                await self.db.execute(
                    select(Payment).where(Payment.idempotency_key == key)
                )
            ).scalar_one()

        # Real on-chain settlement is "armed" when a funded platform signer
        # is configured (the provider initialised as the real x402 client,
        # name == "x402"). When armed, even trial-credit spend settles for
        # REAL on Solana: the platform funds the on-chain USDC transfer and
        # debits the user's trial credit as their accounting balance — a real
        # tx hash lands on the ledger. Unarmed → honest mock (no funds move,
        # tx_hash null, UI shows "Trial credit"). Switching is just the key.
        live = getattr(self.provider, "name", "mock") == "x402"
        if user_provider is not None:
            # Credit exhausted: pay from the user's own delegated wallet.
            pay_provider = user_provider
        elif from_credit and not live:
            from app.x402.provider import MockPaymentProvider  # noqa: PLC0415

            pay_provider = MockPaymentProvider()
        else:
            pay_provider = self.provider
        result = await pay_provider.pay_and_fetch(
            method, url, json=json, headers=headers,
            terms=terms, idempotency_key=key,
        )

        if result.success and result.tx_hash:
            payment.status = PaymentStatus.settled
            if user_provider is not None:
                # Paid from the user's OWN Privy wallet (real on-chain) —
                # trial credit untouched (it was already 0).
                payment.tx_hash = result.tx_hash
                payment.facilitator_ref = result.facilitator_ref
                payment.reconcile_note = (
                    "paid from your own wallet (on-chain)"
                )
            elif from_credit and not live:
                # Unarmed: platform-covered trial credit, NOT an on-chain tx.
                # Store no fake hash. UI shows "Trial credit".
                payment.tx_hash = None
                payment.facilitator_ref = "platform-credit"
                payment.reconcile_note = "platform trial credit (mock — no funded signer)"
                user.credit_remaining = (
                    Decimal(str(user.credit_remaining)) - terms.amount
                )
            elif from_credit and live:
                # Armed: REAL on-chain settlement, platform-funded. The
                # user's trial credit is their accounting balance; a real
                # Solana tx hash is recorded and explorer-verifiable.
                payment.tx_hash = result.tx_hash
                payment.facilitator_ref = result.facilitator_ref
                payment.reconcile_note = (
                    "on-chain settlement (platform-funded; debited from "
                    "your trial credit)"
                )
                user.credit_remaining = (
                    Decimal(str(user.credit_remaining)) - terms.amount
                )
            else:
                # Paid from the user's own wallet → real on-chain tx hash.
                payment.tx_hash = result.tx_hash
                payment.facilitator_ref = result.facilitator_ref
                payment.reconcile_note = "paid from wallet (on-chain)"
            call.paid = True
            call.outcome = "ok"
            await self._update_run_totals(ctx.run_id, terms.amount)
        elif result.success and not result.tx_hash:
            # Served without an on-chain settlement record — do not claim spend.
            payment.status = PaymentStatus.failed
            payment.reconcile_note = "no settlement header; not counted as spend"
            call.outcome = "ok"
        else:
            payment.status = PaymentStatus.failed
            payment.reconcile_note = result.error or "facilitator declined"
            call.outcome = "error"

        call.status_code = result.status_code or 402
        call.latency_ms = int((time.perf_counter() - started) * 1000)
        await self._commit()

        if payment.status == PaymentStatus.settled:
            await self._emit(
                ctx.run_id, "payment_settled",
                api_call_id=call.id, payment_id=payment.id,
                amount=str(terms.amount), tx_hash=payment.tx_hash,
                purpose=ctx.purpose, url=url,
            )
        else:
            await self._emit(
                ctx.run_id, "payment_failed",
                api_call_id=call.id, amount=str(terms.amount),
                reason=payment.reconcile_note,
            )
        return PaidResponse(
            call.status_code, result.text, call.paid, call.outcome,
            terms.amount, payment.tx_hash, call.id,
        )

    async def _update_run_totals(self, run_id: str, add_amount: Decimal) -> None:
        run = (
            await self.db.execute(select(Run).where(Run.id == run_id))
        ).scalar_one()
        run.total_calls += 1
        run.total_spend = Decimal(str(run.total_spend)) + add_amount

    async def _commit(self) -> None:
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
