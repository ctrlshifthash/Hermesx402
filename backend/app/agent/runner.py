"""Agent execution layer.

`AgentRunner` is the interface the worker drives. Two implementations:

* `ScriptedAgentRunner` — deterministic build-stage agent. It is NOT a fake of
  the payment path: it genuinely plans, then drives real HTTP through the real
  `PaidHttpClient`, so the entire request→402→budget→pay→log→stream→dashboard
  pipeline executes for real (against the mock paid API + mock facilitator).
  Only the *reasoning model* is scripted.

* Real Hermes — exposed via the MCP server in `app/agent/mcp_server.py`. Hermes
  natively connects to MCP servers, so the path-to-real (Phase 2 R1) is:
  point a Hermes agent at our MCP server's `paid_http_request` tool and set
  `agent.config_json.runner = "hermes"`. See README "Path to real".

Why MCP over an in-proc tool for the real path: Hermes runs as its own
process/CLI; MCP is its first-class, process-isolated extension boundary, which
also keeps the server-custodied signer out of the model process. The scripted
runner uses the in-proc client directly (no IPC) since it shares our process.
"""
from __future__ import annotations

import asyncio
import json
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.plan import build_plan
from app.models import Agent, Run
from app.services.events import hub
from app.x402.provider import get_payment_provider
from app.x402.wrapper import CallContext, PaidHttpClient


class AgentRunner(Protocol):
    async def run(self, db: AsyncSession, run: Run, agent: Agent) -> str: ...


class ScriptedAgentRunner:
    async def run(self, db: AsyncSession, run: Run, agent: Agent) -> str:
        async def emit(kind: str, **data) -> None:
            await hub.publish(run.id, {"kind": kind, "data": data})

        await emit("reasoning", text=f"Goal received: {run.goal}")
        await asyncio.sleep(0.4)

        plan = build_plan(run.goal)
        await emit("reasoning", text=f"Plan: {len(plan)} step(s).")

        client = PaidHttpClient(db, get_payment_provider())
        results: list[str] = []
        paid_count = 0

        for i, step in enumerate(plan, 1):
            await emit(
                "reasoning",
                text=f"Step {i}/{len(plan)}: {step.thought}",
            )
            await asyncio.sleep(0.3)
            ctx = CallContext(
                user_id=run.user_id,
                wallet_id=run.wallet_id,
                run_id=run.id,
                agent_id=agent.id,
                purpose=step.purpose,
            )
            resp = await client.request(
                step.method, step.url, ctx, json=step.body
            )
            if resp.outcome == "blocked_budget":
                await emit(
                    "reasoning",
                    text=(
                        f"Step {i} blocked by budget guardrail — skipping "
                        f"this data source and continuing."
                    ),
                )
                continue
            if resp.paid:
                paid_count += 1
            try:
                summary = json.loads(resp.text).get("summary", resp.text[:120])
            except Exception:  # noqa: BLE001
                summary = resp.text[:120]
            results.append(summary)
            await emit(
                "reasoning",
                text=f"Step {i} done ({resp.status_code}): {summary}",
            )
            await asyncio.sleep(0.3)

        verdict = (
            f"Completed '{run.goal}'. Consulted {len(results)} data source(s), "
            f"paid for {paid_count}. Findings: "
            + " | ".join(results[:4])
            if results
            else f"No data sources were affordable within budget for '{run.goal}'."
        )
        await emit("reasoning", text=verdict)
        return verdict


def get_runner(agent: Agent) -> AgentRunner:
    from app.core.config import settings  # noqa: PLC0415

    try:
        cfg = json.loads(agent.config_json or "{}")
    except json.JSONDecodeError:
        cfg = {}
    runner = cfg.get("runner")

    if runner == "scripted":
        return ScriptedAgentRunner()
    if runner == "hermes-cli":
        from app.agent.hermes_runner import HermesAgentRunner  # noqa: PLC0415

        return HermesAgentRunner()
    # Real LLM (Nous Hermes on OpenRouter) for "openrouter"/"hermes"/"llm",
    # and as the default whenever an OpenRouter key is configured.
    if runner in ("openrouter", "hermes", "llm") or (
        runner is None and settings.openrouter_api_key
    ):
        from app.agent.openrouter_runner import (  # noqa: PLC0415
            OpenRouterAgentRunner,
        )

        return OpenRouterAgentRunner()
    return ScriptedAgentRunner()
