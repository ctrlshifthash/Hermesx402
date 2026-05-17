"""Real Hermes runner (Phase 2 R1).

Hermes Agent is CLI-first and connects to MCP servers for custom capabilities.
This runner drives a real Hermes agent process, pointed at our MCP server
(`app.agent.mcp_server`) which exposes `paid_http_request`. Every tool call the
model makes flows through the SAME `PaidHttpClient` (budget gate, idempotent
pay, audit, WS streaming) — the money guarantees are runner-independent.

It is enabled by `agent.config_json.runner == "hermes"` and requires the
`hermes` CLI on PATH plus a model key in the environment (HERMES_API_KEY /
provider key). If those are absent it raises a clear, actionable error rather
than silently faking a run — honesty over a fake green path.

Without credentials this code path is not exercised in the local/mock build;
it is the concrete, wired enablement point, not a stub of the payment logic.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Agent, Run
from app.services.events import hub

logger = get_logger("agent.hermes")


def _mcp_config(run: Run, agent: Agent) -> dict:
    """MCP server config Hermes will load. The server binds run/user context
    so tool calls are attributed and budget-scoped to this run."""
    return {
        "mcpServers": {
            "agentledger-x402": {
                "command": "python",
                "args": ["-m", "app.agent.mcp_server"],
                "env": {
                    "AGENTLEDGER_USER_ID": run.user_id,
                    "AGENTLEDGER_WALLET_ID": run.wallet_id,
                    "AGENTLEDGER_RUN_ID": run.id,
                    "AGENTLEDGER_AGENT_ID": agent.id,
                    "DATABASE_URL": settings.database_url,
                    "PAYMENT_PROVIDER": settings.payment_provider,
                },
            }
        }
    }


class HermesAgentRunner:
    async def run(self, db: AsyncSession, run: Run, agent: Agent) -> str:
        if shutil.which("hermes") is None:
            raise RuntimeError(
                "Hermes runner selected but the `hermes` CLI is not on PATH. "
                "Install hermes-agent and set the model key, or use the "
                "scripted runner (agent.config_json.runner='scripted'). "
                "See README 'Path to real' R1."
            )
        if not (os.getenv("HERMES_API_KEY") or os.getenv("OPENAI_API_KEY")):
            raise RuntimeError(
                "Hermes runner needs a model API key (HERMES_API_KEY). "
                "Provide it via env to enable real reasoning."
            )

        async def emit(kind: str, **data) -> None:
            await hub.publish(run.id, {"kind": kind, "data": data})

        await emit("reasoning", text=f"Starting Hermes agent for: {run.goal}")

        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as cfg:
            json.dump(_mcp_config(run, agent), cfg)
            cfg_path = cfg.name

        # Instruct Hermes to use the paid_http_request MCP tool for any
        # external data and to respect 402 paywalls automatically.
        prompt = (
            f"{run.goal}\n\n"
            "Use the `paid_http_request` MCP tool for ALL external data. "
            "It auto-pays x402 paywalls within the user's budget; "
            "over-budget calls are blocked — do not retry those, move on."
        )
        proc = await asyncio.create_subprocess_exec(
            "hermes", "run", "--mcp-config", cfg_path, "--prompt", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        last = ""
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line:
                last = line
                await emit("reasoning", text=line)
        await proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(f"Hermes exited {proc.returncode}: {last}")
        return f"Hermes completed '{run.goal}'. {last[:240]}"
