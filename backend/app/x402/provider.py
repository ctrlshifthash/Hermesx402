"""Payment provider abstraction — the mock↔real seam (feature flag R10).

The wrapper enforces budget BEFORE a provider is ever asked to pay, then calls
`pay_and_fetch` exactly once per logical step (idempotency guaranteed by a
unique DB row claimed first). Two implementations:

* `MockPaymentProvider` — permitted build-stage scaffolding. No money moves;
  deterministic synthetic tx hash; replays the request with a mock X-PAYMENT
  header so the mock paid API serves data.

* `X402PaymentProvider` — the real path, using the actual Coinbase `x402`
  Python SDK (verified against coinbase/x402 examples):

      from x402 import x402ClientSync
      from x402.http import x402HTTPClientSync
      from x402.http.clients import x402_requests
      from x402.mechanisms.evm import EthAccountSigner
      from x402.mechanisms.evm.exact.register import register_exact_evm_client

  `x402_requests(client)` returns a requests-style session that performs the
  402 → pay → retry exchange internally against the real facilitator/network.
  Because that auto-pays, the budget gate MUST run before we call it — which is
  exactly what the wrapper guarantees. We then read the settlement header for
  the real tx hash. Imports are lazy so the mock install stays offline-lean.

Switching is one env var (`PAYMENT_PROVIDER`); nothing else changes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("x402.provider")


@dataclass(frozen=True)
class PaymentRequired:
    """Parsed terms from an HTTP 402 response."""

    amount: Decimal
    currency: str
    network: str
    pay_to: str
    raw: dict


@dataclass(frozen=True)
class PayResult:
    """Outcome of paying for and fetching the resource."""

    success: bool
    status_code: int
    text: str
    tx_hash: str | None
    facilitator_ref: str | None
    error: str | None = None


class ProviderError(RuntimeError):
    pass


class PaymentProvider(Protocol):
    name: str

    def parse_402(self, response: httpx.Response) -> PaymentRequired: ...

    async def pay_and_fetch(
        self,
        method: str,
        url: str,
        *,
        json: dict | None,
        headers: dict,
        terms: PaymentRequired,
        idempotency_key: str,
    ) -> PayResult: ...


def parse_x402_terms(response: httpx.Response) -> PaymentRequired:
    """Parse x402 payment requirements. Handles v1 (JSON body `accepts`) AND
    v2 (requirements moved into the base64 `payment-required` header with an
    empty body) — the budget gate must read the amount either way."""
    accepts: list = []
    try:
        body = response.json()
        accepts = body.get("accepts") or body.get("paymentRequirements") or []
    except Exception:  # noqa: BLE001
        accepts = []

    if not accepts:
        # x402-v2: requirements are in a base64-encoded response header.
        import base64  # noqa: PLC0415
        import json as _json  # noqa: PLC0415

        for hk in ("payment-required", "x-payment-required",
                   "www-authenticate"):
            hv = response.headers.get(hk)
            if not hv:
                continue
            try:
                payload = _json.loads(base64.b64decode(hv))
                accepts = (
                    payload.get("accepts")
                    or payload.get("paymentRequirements")
                    or []
                )
                if accepts:
                    break
            except Exception:  # noqa: BLE001
                continue

    if not accepts:
        raise ProviderError("402 response had no payment requirements")
    terms = accepts[0]
    decimals = int(terms.get("extra", {}).get("decimals", 6))
    raw_amt = Decimal(str(terms.get("maxAmountRequired", terms.get("amount", "0"))))
    return PaymentRequired(
        amount=raw_amt / (Decimal(10) ** decimals),
        currency=terms.get("extra", {}).get("name", "USDC"),
        network=terms.get("network", settings.x402_network),
        pay_to=terms.get("payTo", ""),
        raw=terms,
    )


class MockPaymentProvider:
    """No money moves. Deterministic so retries are naturally idempotent."""

    name = "mock"

    def parse_402(self, response: httpx.Response) -> PaymentRequired:
        return parse_x402_terms(response)

    async def pay_and_fetch(
        self,
        method: str,
        url: str,
        *,
        json: dict | None,
        headers: dict,
        terms: PaymentRequired,
        idempotency_key: str,
    ) -> PayResult:
        digest = hashlib.sha256(
            f"{idempotency_key}:{terms.amount}:{terms.pay_to}".encode()
        ).hexdigest()
        tx = "0xmock" + digest[:58]
        proof = dict(headers)
        proof["X-PAYMENT"] = f"mock-payment {digest[:32]}"
        async with httpx.AsyncClient(
            timeout=30.0, transport=_mock_transport()
        ) as http:
            resp = await http.request(method, url, json=json, headers=proof)
        logger.info(
            "mock settlement",
            extra={"extra_fields": {"tx_hash": tx, "amount": str(terms.amount)}},
        )
        return PayResult(
            success=resp.is_success,
            status_code=resp.status_code,
            text=resp.text,
            tx_hash=tx,
            facilitator_ref=f"mock-{digest[:16]}",
        )


# Lets the test suite route the mock provider's replay to the in-process app.
_MOCK_TRANSPORT: httpx.AsyncBaseTransport | None = None


def set_mock_transport(t: httpx.AsyncBaseTransport | None) -> None:
    global _MOCK_TRANSPORT
    _MOCK_TRANSPORT = t


def _mock_transport() -> httpx.AsyncBaseTransport | None:
    return _MOCK_TRANSPORT


class X402PaymentProvider:
    """Real path. Lazy-imports the SDK; only reached after the budget gate."""

    name = "x402"

    def __init__(self, svm_signer=None) -> None:  # noqa: ANN001
        from x402 import x402ClientSync  # noqa: PLC0415
        from x402.http import x402HTTPClientSync  # noqa: PLC0415

        client = x402ClientSync()
        net = (settings.x402_network or "").lower()

        if net.startswith("solana"):
            # --- Solana (SVM) path ---
            from x402.mechanisms.svm.exact.register import (  # noqa: PLC0415
                register_exact_svm_client,
            )

            if svm_signer is not None:
                # Per-user: sign with the caller's delegated Privy wallet.
                signer = svm_signer
            else:
                if not settings.x402_svm_private_key:
                    raise ProviderError(
                        "x402 network is Solana but X402_SVM_PRIVATE_KEY "
                        "is unset"
                    )
                from x402.mechanisms.svm import (  # noqa: PLC0415
                    KeypairSigner,
                )

                signer = KeypairSigner.from_base58(
                    settings.x402_svm_private_key
                )
            register_exact_svm_client(client, signer)
            self.address = getattr(signer, "address", "svm")
        else:
            # --- EVM (Base/Ethereum) path ---
            if not settings.x402_evm_private_key:
                raise ProviderError(
                    "x402 network is EVM but X402_EVM_PRIVATE_KEY is unset"
                )
            from eth_account import Account  # noqa: PLC0415
            from x402.mechanisms.evm import EthAccountSigner  # noqa: PLC0415
            from x402.mechanisms.evm.exact.register import (  # noqa: PLC0415
                register_exact_evm_client,
            )

            account = Account.from_key(settings.x402_evm_private_key)
            register_exact_evm_client(client, EthAccountSigner(account))
            self.address = account.address

        self._client = client
        self._http_client = x402HTTPClientSync(client)
        logger.info(
            "x402 provider initialised",
            extra={"extra_fields": {"address": self.address,
                                    "network": settings.x402_network}},
        )

    def parse_402(self, response: httpx.Response) -> PaymentRequired:
        return parse_x402_terms(response)

    async def pay_and_fetch(
        self,
        method: str,
        url: str,
        *,
        json: dict | None,
        headers: dict,
        terms: PaymentRequired,
        idempotency_key: str,
    ) -> PayResult:
        """Perform the budget-approved request via the x402 session.

        The session pays the 402 against the real facilitator and retries
        internally; we then read the settlement header for the real tx hash.
        Runs in a thread (the SDK session is sync).
        """
        import anyio  # noqa: PLC0415

        def _do() -> PayResult:
            from x402.http.clients import x402_requests  # noqa: PLC0415

            with x402_requests(self._client) as session:
                if method.upper() == "GET":
                    resp = session.get(url, headers=headers, timeout=60)
                else:
                    resp = session.request(
                        method, url, json=json, headers=headers, timeout=60
                    )
            tx_hash = None
            facilitator_ref = None
            try:
                settle = self._http_client.get_payment_settle_response(
                    lambda n: resp.headers.get(n)
                )
                data = settle.model_dump()
                tx_hash = (
                    data.get("transaction")
                    or data.get("txHash")
                    or data.get("tx_hash")
                )
                facilitator_ref = data.get("payer") or data.get("network")
            except ValueError:
                # No settlement header — server served without charging, or
                # the SDK declined. Treat as unpaid-but-fetched.
                pass
            return PayResult(
                success=200 <= resp.status_code < 300,
                status_code=resp.status_code,
                text=resp.text,
                tx_hash=tx_hash,
                facilitator_ref=facilitator_ref,
                error=None if 200 <= resp.status_code < 300 else resp.text[:300],
            )

        try:
            return await anyio.to_thread.run_sync(_do)
        except Exception as exc:  # noqa: BLE001
            logger.exception("x402 pay_and_fetch failed")
            return PayResult(False, 0, "", None, None, error=str(exc))


@lru_cache(maxsize=1)
def facilitator_fee_payer() -> str | None:
    """The SVM fee-payer the facilitator will co-sign with. On Solana the
    facilitator sponsors the SOL gas and submits the tx, so its feePayer
    pubkey MUST be embedded in the 402 `extra`. Discovered live from the
    facilitator's /supported (cached); explicit override wins."""
    if settings.x402_fee_payer:
        return settings.x402_fee_payer
    try:
        from x402.mechanisms.svm.constants import (  # noqa: PLC0415
            V1_TO_V2_NETWORK_MAP,
        )

        caip = V1_TO_V2_NETWORK_MAP.get(
            settings.x402_network, settings.x402_network
        )
        r = httpx.get(
            settings.x402_facilitator_url.rstrip("/") + "/supported",
            follow_redirects=True,
            timeout=12,
        )
        for k in r.json().get("kinds", []):
            if k.get("scheme") == "exact" and k.get("network") == caip:
                fp = (k.get("extra") or {}).get("feePayer")
                if fp:
                    logger.info(
                        "facilitator fee payer discovered",
                        extra={"extra_fields": {"fee_payer": fp,
                                                "network": caip}},
                    )
                    return fp
    except Exception as exc:  # noqa: BLE001
        logger.warning("fee payer discovery failed: %s", exc)
    return None


@lru_cache(maxsize=1)
def settlement_status() -> dict:
    """Is REAL on-chain settlement armed? Cached (one process = one answer;
    a key change needs a restart anyway). Honest: reports the exact reason
    it's falling back to mock so nothing is silently faked."""
    if settings.payment_provider != "x402":
        return {"mode": "mock", "reason": "PAYMENT_PROVIDER is not 'x402'"}
    try:
        p = X402PaymentProvider()
        return {
            "mode": "live",
            "network": settings.x402_network,
            "pay_to": settings.x402_pay_to,
            "signer": getattr(p, "address", None),
        }
    except Exception as exc:  # noqa: BLE001
        return {"mode": "mock", "reason": str(exc)[:200]}


def build_user_delegated_provider(wallet_id: str, address: str):
    """An x402 provider that pays from the USER'S delegated Privy wallet
    (used once their trial credit is exhausted). None if not on the real
    Solana path. Never touches the platform key."""
    if settings.payment_provider != "x402":
        return None
    if not (settings.x402_network or "").lower().startswith("solana"):
        return None
    from app.core.privy_signer import PrivyDelegatedSigner  # noqa: PLC0415

    return X402PaymentProvider(
        svm_signer=PrivyDelegatedSigner(wallet_id, address)
    )


def build_browser_signed_provider(run_id: str, address: str, loop):
    """x402 provider that gets the payer signature from the user's BROWSER
    wallet at spend time (approve-at-spend). None if not on the Solana path.
    Never touches any key."""
    if settings.payment_provider != "x402":
        return None
    if not (settings.x402_network or "").lower().startswith("solana"):
        return None
    from app.x402.browser_signer import BrowserSigner  # noqa: PLC0415

    return X402PaymentProvider(
        svm_signer=BrowserSigner(run_id, address, loop)
    )


def get_payment_provider() -> PaymentProvider:
    if settings.payment_provider == "x402":
        try:
            return X402PaymentProvider()
        except Exception as exc:  # noqa: BLE001
            # No funded platform signer for the configured network yet →
            # keep the app working on the mock seam (trial credit is
            # mock-settled anyway). Real settlement activates the moment the
            # signer key is provided. Logged, not hidden.
            logger.warning(
                "x402 provider unavailable; using mock settlement",
                extra={"extra_fields": {"reason": str(exc)}},
            )
            return MockPaymentProvider()
    return MockPaymentProvider()
