"""Pre-flight for the real money path — verifies WITHOUT moving funds.

    python -m scripts.check_real

Checks: real x402 SDK importable, signer derivable, facilitator reachable,
Hermes CLI present. Green here means `PAYMENT_PROVIDER=x402` + a Hermes agent
will work when you flip the flag. It never signs or sends a transaction.
"""
from __future__ import annotations

import shutil
import sys

import httpx

from app.core.config import settings


def main() -> int:
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and cond
        print(f"[{'PASS' if cond else 'FAIL'}] {name}{' — ' + detail if detail else ''}")

    print(f"payment_provider = {settings.payment_provider}")
    print(f"network          = {settings.x402_network}\n")

    try:
        import x402  # noqa: F401
        from x402 import x402ClientSync  # noqa: F401
        from x402.mechanisms.evm import EthAccountSigner  # noqa: F401

        check("x402 SDK import", True, x402.__name__)
    except Exception as exc:  # noqa: BLE001
        check("x402 SDK import", False, f"pip install x402 eth-account ({exc})")

    if settings.x402_evm_private_key:
        try:
            from eth_account import Account

            addr = Account.from_key(settings.x402_evm_private_key).address
            check("EVM signer", True, f"address {addr}")
        except Exception as exc:  # noqa: BLE001
            check("EVM signer", False, str(exc))
    else:
        check("EVM signer", False, "X402_EVM_PRIVATE_KEY unset")

    try:
        r = httpx.get(settings.x402_facilitator_url, timeout=8)
        check("facilitator reachable", r.status_code < 500,
              f"{settings.x402_facilitator_url} → {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        check("facilitator reachable", False, str(exc))

    # Agent reasoning: OpenRouter (default) OR the optional hermes CLI.
    if settings.openrouter_api_key:
        check("agent LLM", True, f"OpenRouter · {settings.openrouter_model}")
    else:
        check("agent LLM", shutil.which("hermes") is not None,
              "set OPENROUTER_API_KEY or install hermes-agent")

    print("\n" + ("ALL GREEN — safe to set PAYMENT_PROVIDER=x402"
                   if ok else "Not ready — fix FAILs above. No funds were touched."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
