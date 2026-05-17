"""MCP server exposing the x402 wrapper as a tool for real Hermes.

Run standalone:  python -m app.agent.mcp_server
Then point a Hermes agent's MCP config at it. Hermes calls `paid_http_request`;
the call flows through the *same* `PaidHttpClient` (budget enforcement,
idempotent pay, logging, WS streaming) the scripted runner uses. This is the
concrete path-to-real for R1 — the payment/budget/audit guarantees do not
depend on which runner is driving.

Kept import-lazy: the `mcp` package is only needed when actually running the
Hermes path, so local/mock installs don't require it.
"""
from __future__ import annotations

import asyncio

from app.db.session import SessionLocal
from app.x402.provider import get_payment_provider
from app.x402.wrapper import CallContext, PaidHttpClient


async def _paid_http_request(
    method: str, url: str, user_id: str, wallet_id: str, run_id: str,
    agent_id: str, purpose: str, body: dict | None = None,
) -> dict:
    async with SessionLocal() as db:
        client = PaidHttpClient(db, get_payment_provider())
        resp = await client.request(
            method,
            url,
            CallContext(user_id=user_id, wallet_id=wallet_id, run_id=run_id,
                        agent_id=agent_id, purpose=purpose),
            json=body,
        )
        return {
            "status_code": resp.status_code,
            "paid": resp.paid,
            "outcome": resp.outcome,
            "amount": str(resp.amount) if resp.amount is not None else None,
            "tx_hash": resp.tx_hash,
            "body": resp.text,
        }


def main() -> None:
    import os  # noqa: PLC0415

    from mcp.server.fastmcp import FastMCP  # noqa: PLC0415

    mcp = FastMCP("agentledger-x402")
    # Run/user context is bound by the HermesAgentRunner via env so the model
    # cannot spoof attribution or escape its run's budget scope.
    USER = os.environ["AGENTLEDGER_USER_ID"]
    WALLET = os.environ["AGENTLEDGER_WALLET_ID"]
    RUN = os.environ["AGENTLEDGER_RUN_ID"]
    AGENT = os.environ["AGENTLEDGER_AGENT_ID"]

    @mcp.tool()
    async def paid_http_request(  # noqa: D401
        method: str, url: str, purpose: str, body: dict | None = None,
    ) -> dict:
        """Make an HTTP request that auto-pays x402 paywalls within budget.

        Use for any external data/API. If the resource costs money the agent's
        wallet pays automatically *iff* within the user's budget caps;
        over-budget calls are blocked and reported, not paid. `purpose` is a
        short human-readable reason, shown in the user's audit ledger.
        """
        return await _paid_http_request(
            method, url, USER, WALLET, RUN, AGENT, purpose, body
        )

    mcp.run()


if __name__ == "__main__":
    main()
