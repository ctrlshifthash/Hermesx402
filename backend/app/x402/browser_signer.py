"""x402 SVM signer that asks the user's BROWSER to sign at spend time.

Reuses the same `ClientSvmSigner` seam as the platform/Privy signers. When
x402 needs the payer's signature, this publishes a `payment_sign_request`
event on the run's WebSocket, blocks until the browser POSTs the signature
back (see /runs/{id}/sign), then returns it as a solders Signature. The
server never holds the key — the user signs in their own wallet.
"""
from __future__ import annotations

import asyncio
import base64

from solders.pubkey import Pubkey
from solders.signature import Signature

from app.core.logging import get_logger
from app.services.events import hub
from app.x402 import pending

logger = get_logger("x402.browser_signer")

# Generous: the human has to see the prompt and click approve in-wallet.
_APPROVAL_TIMEOUT = 150.0


class _BrowserKeypair:
    """Duck-typed Keypair: x402's exact-SVM client only calls pubkey() and
    sign_message(bytes). sign_message round-trips to the browser."""

    def __init__(self, run_id: str, address: str, loop) -> None:
        self._run_id = run_id
        self._pubkey = Pubkey.from_string(address)
        self._loop = loop

    def pubkey(self) -> Pubkey:
        return self._pubkey

    def sign_message(self, msg: bytes) -> Signature:
        token = pending.open_request()
        evt = {
            "kind": "payment_sign_request",
            "data": {
                "token": token,
                "message_b64": base64.b64encode(msg).decode(),
                "address": str(self._pubkey),
            },
        }
        # We're inside a worker thread; publish on the API event loop.
        fut = asyncio.run_coroutine_threadsafe(
            hub.publish(self._run_id, evt), self._loop
        )
        fut.result(timeout=10)
        logger.info("awaiting in-browser signature",
                    extra={"extra_fields": {"run_id": self._run_id}})
        raw = pending.wait(token, _APPROVAL_TIMEOUT)
        return Signature.from_bytes(raw)


class BrowserSigner:
    """ClientSvmSigner backed by the user's browser wallet."""

    def __init__(self, run_id: str, address: str, loop) -> None:
        self._kp = _BrowserKeypair(run_id, address, loop)
        self._address = address

    @property
    def address(self) -> str:
        return self._address

    @property
    def keypair(self):  # noqa: ANN201 - duck-typed on purpose
        return self._kp

    def sign_transaction(self, tx):  # noqa: ANN001, ANN201
        msg = bytes(tx.message.to_bytes_versioned())
        tx.signatures = [self._kp.sign_message(msg), *list(tx.signatures)[1:]]
        return tx
