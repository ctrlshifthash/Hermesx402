"""Pay from the USER'S OWN Privy wallet — without the server ever holding
their key.

When a user's trial credit is exhausted, the agent must pay from their
wallet. Privy never exposes private keys, so instead the user delegates
signing to the app once (Privy "delegated actions"). After that, the server
can ask Privy's REST API to sign on the user's behalf.

x402's exact-SVM client signs by calling `signer.keypair.sign_message(bytes)`
and reading `signer.address`. We provide a `ClientSvmSigner` whose `.keypair`
is a thin remote proxy: `sign_message` POSTs the bytes to Privy's wallet RPC
(`/v1/wallets/{id}/rpc` → `signMessage`) and returns the real ed25519
`Signature`. No key material is ever on our side.
"""
from __future__ import annotations

import base64

import httpx
from solders.pubkey import Pubkey
from solders.signature import Signature

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("privy.signer")

_PRIVY_API = "https://api.privy.io/v1"


def _auth() -> tuple[str, str]:
    if not (settings.privy_app_id and settings.privy_app_secret):
        raise RuntimeError("Privy app id/secret not configured")
    return (settings.privy_app_id, settings.privy_app_secret)


class _RemoteKeypair:
    """Duck-typed stand-in for solders.Keypair: only the two members the
    x402 exact-SVM client actually touches — `pubkey()` and
    `sign_message(bytes) -> Signature` — backed by Privy, not a local key."""

    def __init__(self, wallet_id: str, address: str) -> None:
        self._wallet_id = wallet_id
        self._pubkey = Pubkey.from_string(address)

    def pubkey(self) -> Pubkey:
        return self._pubkey

    def sign_message(self, msg: bytes) -> Signature:
        body = {
            "method": "signMessage",
            "params": {
                "message": base64.b64encode(msg).decode(),
                "encoding": "base64",
            },
        }
        r = httpx.post(
            f"{_PRIVY_API}/wallets/{self._wallet_id}/rpc",
            auth=_auth(),
            headers={"privy-app-id": settings.privy_app_id or ""},
            json=body,
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Privy sign failed {r.status_code}: {r.text[:300]}"
            )
        data = r.json().get("data") or r.json()
        sig_b64 = data.get("signature") or data.get("signedMessage")
        if not sig_b64:
            raise RuntimeError(f"Privy sign: no signature in {r.text[:200]}")
        raw = base64.b64decode(sig_b64)
        return Signature.from_bytes(raw)


class PrivyDelegatedSigner:
    """x402 ClientSvmSigner backed by a user's delegated Privy wallet."""

    def __init__(self, wallet_id: str, address: str) -> None:
        self._kp = _RemoteKeypair(wallet_id, address)
        self._address = address

    @property
    def address(self) -> str:
        return self._address

    @property
    def keypair(self):  # noqa: ANN201 - duck-typed on purpose
        return self._kp

    def sign_transaction(self, tx):  # noqa: ANN001, ANN201
        # The exact-SVM scheme signs via keypair.sign_message; this is only a
        # fallback for code paths that sign whole transactions.
        msg = bytes(tx.message.to_bytes_versioned())
        sig = self._kp.sign_message(msg)
        tx.signatures = [sig, *list(tx.signatures)[1:]]
        return tx
