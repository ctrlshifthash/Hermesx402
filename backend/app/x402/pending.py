"""Pending in-browser signature requests.

When trial credit is exhausted the agent must pay from the user's own
wallet. The user signs in their browser at spend time, so the server-side
signer pauses and waits here for the signature to come back via an API call.

Thread-safe: the x402 SVM client signs inside a worker thread, while the
signature arrives on the async API. A plain threading primitive bridges the
two without needing the event loop.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field


@dataclass
class _Pending:
    event: threading.Event = field(default_factory=threading.Event)
    signature: bytes | None = None
    error: str | None = None


_REGISTRY: dict[str, _Pending] = {}
_LOCK = threading.Lock()


def open_request() -> str:
    token = "sig_" + uuid.uuid4().hex
    with _LOCK:
        _REGISTRY[token] = _Pending()
    return token


def wait(token: str, timeout: float) -> bytes:
    with _LOCK:
        p = _REGISTRY.get(token)
    if p is None:
        raise RuntimeError("unknown signature request")
    if not p.event.wait(timeout):
        with _LOCK:
            _REGISTRY.pop(token, None)
        raise TimeoutError("user did not approve the payment in time")
    with _LOCK:
        _REGISTRY.pop(token, None)
    if p.error:
        raise RuntimeError(p.error)
    if p.signature is None:
        raise RuntimeError("no signature provided")
    return p.signature


def resolve(token: str, signature: bytes | None, error: str | None = None) -> bool:
    with _LOCK:
        p = _REGISTRY.get(token)
        if p is None:
            return False
        p.signature = signature
        p.error = error
        p.event.set()
    return True
