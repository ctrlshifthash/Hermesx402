"""Deterministic goal → plan compiler for the scripted runner.

Turns a free-text goal into concrete steps that hit the x402-gated mock API.
Real Hermes replaces this with model reasoning; the *step shape*
(thought/purpose/url/method/body) is exactly what the MCP tool exposes, so the
contract is identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class Step:
    thought: str
    purpose: str
    url: str
    method: str = "GET"
    body: dict | None = field(default=None)


def build_plan(goal: str) -> list[Step]:
    base = settings.mock_api_base_url.rstrip("/")
    g = goal.lower()
    steps: list[Step] = [
        Step(
            thought="Establish baseline context (free endpoint, no payment).",
            purpose="Baseline context lookup",
            url=f"{base}/free/context",
        )
    ]
    topics = []
    if "gpu" in g or "hardware" in g:
        topics = ["gpu-prices", "gpu-benchmarks"]
    elif "weather" in g or "climate" in g:
        topics = ["weather", "climate-history"]
    elif "stock" in g or "market" in g or "crypto" in g:
        topics = ["market-quote", "market-news"]
    else:
        topics = ["web-search", "knowledge-base"]
    for t in topics:
        steps.append(
            Step(
                thought=f"Need premium '{t}' data — provider gates it behind x402.",
                purpose=f"Premium {t.replace('-', ' ')} for: {goal[:80]}",
                url=f"{base}/paid/{t}",
            )
        )
    steps.append(
        Step(
            thought="Cross-check with a second premium source for confidence.",
            purpose=f"Premium cross-check for: {goal[:80]}",
            url=f"{base}/paid/cross-check",
        )
    )
    return steps
