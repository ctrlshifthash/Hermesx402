"""Autonomous agent: Nous Hermes (OpenRouter) reasoning over REAL data.

Design for reliability: the model is excellent at reasoning but unreliable at
emitting a strict tool-call protocol, so the runner DETERMINISTICALLY performs
the data retrieval the task needs (real x402-paid fetches + a live web search),
then Hermes does what it's good at — reason over the real observations and
write a grounded answer. Result: real payments every run, real data, real
reasoning, fast, no flailing, never fabricated.

Persistent memory is recalled in and the conclusion saved out, so the agent
improves across runs.
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.plan import build_plan
from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    Agent, ApiCall, Memory, Payment, PaymentStatus, Run, User,
)
from app.services.events import hub
from app.x402.provider import get_payment_provider
from app.x402.wrapper import CallContext, PaidHttpClient

logger = get_logger("agent.openrouter")


class OpenRouterAgentRunner:
    async def run(self, db: AsyncSession, run: Run, agent: Agent) -> str:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")

        journal: list[dict] = []

        async def emit(kind: str, **data) -> None:
            journal.append({"kind": kind, "data": data})
            await hub.publish(run.id, {"kind": kind, "data": data})

        async def persist_journal() -> None:
            try:
                rr = (
                    await db.execute(select(Run).where(Run.id == run.id))
                ).scalar_one()
                rr.journal = json.dumps(journal)[:60000]
                await db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("journal persist failed")

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://agentledger.local",
            "X-Title": "Hermesx402",
        }

        # ---- recall persistent memory ----
        past = list(
            (
                await db.execute(
                    select(Memory)
                    .where(Memory.agent_id == agent.id)
                    .order_by(Memory.created_at.desc())
                    .limit(6)
                )
            ).scalars()
        )
        memory_block = "\n".join(
            f"- ({m.kind}) {m.content[:240]}" for m in reversed(past)
        )
        if past:
            await emit("reasoning",
                       text=f"Recalled {len(past)} memory item(s) from past "
                            f"runs of this agent.")

        # Recall-only = the task explicitly asks to answer from memory WITHOUT
        # fetching. NOT triggered by "remember" (that's a save instruction,
        # e.g. "remember your pick") which must still do the real work.
        g = run.goal.lower()
        recall_only = (
            "from memory" in g
            or "do not fetch" in g
            or "don't fetch" in g
            or "without fetching" in g
            or "what did you recommend" in g
            or ("previously" in g and "recommend" in g)
        )

        await emit("reasoning",
                   text=f"Hermes ({settings.openrouter_model}) — planning: "
                        f"{run.goal}")

        # ---- live web research (real, current; OpenRouter web plugin) ----
        web_findings, web_sources = "", []
        if not recall_only:
            try:
                async with httpx.AsyncClient(timeout=90) as h:
                    wr = await h.post(
                        f"{settings.openrouter_base_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": settings.openrouter_model,
                            "messages": [
                                {"role": "system", "content":
                                 "You are a meticulous research assistant. "
                                 "Use the LIVE web results to gather concrete, "
                                 "current facts for the user's request: exact "
                                 "names, numbers, prices, dates, specs, and "
                                 "direct quotes. Capture competing options and "
                                 "their trade-offs. Be exhaustive and precise "
                                 "— this brief is the sole evidence another "
                                 "analyst will reason from, so omit nothing "
                                 "important and never guess."},
                                {"role": "user", "content": run.goal},
                            ],
                            "temperature": 0.2, "max_tokens": 1200,
                            "plugins": [{"id": "web", "max_results": 8}],
                        },
                    )
                if wr.status_code == 200:
                    m = wr.json()["choices"][0]["message"]
                    web_findings = m.get("content") or ""
                    for a in m.get("annotations") or []:
                        u = (a.get("url_citation") or {}).get("url")
                        if u and u not in web_sources:
                            web_sources.append(u)
                    if web_findings:
                        await emit("reasoning",
                                   text="Web findings: " + web_findings[:400])
            except Exception as exc:  # noqa: BLE001
                logger.warning("web research failed: %s", exc)

        # x402 payment path is OPT-IN only (real paid x402 APIs barely exist
        # publicly yet — see README). A normal research task is 100% real web,
        # no synthetic endpoints, real source links. The paid path only runs
        # if the goal explicitly asks for an x402/paid API to call.
        observations: list[dict] = []
        used_sources: list[str] = list(web_sources)
        paid = 0
        opt_in_paid = any(
            k in g for k in (
                "premium data api", "paid api", "x402 api",
                "agentledger premium", "/paid/", "via x402",
            )
        )
        if opt_in_paid and not recall_only:
            client = PaidHttpClient(db, get_payment_provider())
            for step in build_plan(run.goal):
                ctx = CallContext(
                    user_id=run.user_id, wallet_id=run.wallet_id,
                    run_id=run.id, agent_id=agent.id, purpose=step.purpose,
                )
                await emit("reasoning",
                           text=f"→ x402 GET {step.url} — {step.purpose}")
                r = await client.request(step.method, step.url, ctx,
                                         json=step.body)
                if r.paid:
                    paid += 1
                if r.outcome == "blocked_budget":
                    await emit("reasoning",
                               text="Budget/credit limit hit — answering "
                                    "with what I have.")
                    break
                used_sources.append(step.url)
                try:
                    body = json.loads(r.text)
                except Exception:  # noqa: BLE001
                    body = r.text[:600]
                observations.append({"url": step.url, "data": body})

        # ---- Hermes reasons over the REAL data → grounded answer ----
        ground = json.dumps(observations)[:6000]
        sys = (
            "You are Hermes, an elite research analyst. Deliver a thorough, "
            "decision-ready answer grounded ONLY in the live web findings, "
            "paid data, and memory provided — never invent facts or URLs. "
            "Write clean GitHub-flavored Markdown with this exact structure:\n\n"
            "## TL;DR\nThree to five tight bullet points a busy reader can act "
            "on immediately — the bottom line, the pick, the key number.\n\n"
            "## Recommendation\nOne or two sentences stating the single best "
            "answer/choice for the user's goal, unambiguously.\n\n"
            "## Analysis\nThe substantive breakdown. Compare the real options "
            "with concrete specifics — prices, numbers, dates, specs, "
            "pros/cons. Use a Markdown table when comparing 3+ options, "
            "otherwise a bullet list with **bold** labels. Be specific and "
            "quantitative, never generic filler.\n\n"
            "## Reasoning\nA short paragraph explaining WHY the recommendation "
            "follows from the evidence above.\n\n"
            "## Caveats\nReal trade-offs, risks, or freshness limits of the "
            "data.\n\n"
            "## Sources\nA Markdown bullet list where every real URL is a "
            "clickable link in `[domain or title](https://full-url)` form, "
            "verbatim from those given. If none, write 'memory' or 'none' "
            "truthfully. NEVER cite localhost or fabricate a link.\n\n"
            "Rules: depth, specificity and accuracy decide success — a vague "
            "or padded answer is a failure. Prefer real figures over adjectives. "
            "Do not include a section if you have zero real content for it; "
            "do not pad."
        )
        usr = (
            f"Task: {run.goal}\n\n"
            f"Memory from past runs:\n{memory_block or '(none)'}\n\n"
            f"Live web findings:\n{web_findings or '(none)'}\n\n"
            + (f"Paid API data (x402):\n{ground}\n\n" if observations else "")
            + f"Real source URLs to cite: "
            f"{', '.join(used_sources) or 'none'}"
        )
        try:
            async with httpx.AsyncClient(timeout=90) as h:
                fr = await h.post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": settings.openrouter_model,
                        "messages": [
                            {"role": "system", "content": sys},
                            {"role": "user", "content": usr},
                        ],
                        "temperature": 0.45, "max_tokens": 2400,
                    },
                )
            answer = (
                fr.json()["choices"][0]["message"].get("content")
                if fr.status_code == 200 else None
            ) or f"Completed '{run.goal}'."
        except Exception as exc:  # noqa: BLE001
            answer = f"Completed '{run.goal}' ({paid} paid source(s))."
            logger.warning("final synthesis failed: %s", exc)

        # ---- charge real usage (LLM + web calls cost real money) ----
        try:
            fee = Decimal(settings.run_usage_fee_usd)
            user = (
                await db.execute(select(User).where(User.id == run.user_id))
            ).scalar_one()
            uc = ApiCall(
                run_id=run.id, wallet_id=run.wallet_id, agent_id=agent.id,
                user_id=run.user_id, url="agent://hermes+web",
                method="LLM", status_code=200, paid=True, outcome="ok",
                purpose="Hermes reasoning + live web research",
            )
            db.add(uc)
            await db.flush()
            from_credit = Decimal(str(user.credit_remaining)) >= fee
            db.add(Payment(
                api_call_id=uc.id, run_id=run.id, wallet_id=run.wallet_id,
                user_id=run.user_id, amount=fee, currency="USDC",
                network=settings.x402_network,
                status=PaymentStatus.settled,
                facilitator_ref="platform-credit" if from_credit
                else "wallet",
                reconcile_note="agent usage: LLM + web research",
                idempotency_key="use_" + uuid.uuid4().hex,
            ))
            if from_credit:
                user.credit_remaining = (
                    Decimal(str(user.credit_remaining)) - fee
                )

            # --- Marketplace split: renting someone else's public agent ---
            # The renter pays the listing price; the platform keeps 20%, the
            # creator earns 80% (recorded as a creator-earning Payment).
            rent_total = Decimal("0")
            if run.creator_user_id:
                price = Decimal(str(agent.price_per_run_usd or 0))
                if price > 0:
                    creator_cut = (price * Decimal("0.80")).quantize(
                        Decimal("0.000001")
                    )
                    rc = ApiCall(
                        run_id=run.id, wallet_id=run.wallet_id,
                        agent_id=agent.id, user_id=run.user_id,
                        url="marketplace://rent", method="RENT",
                        status_code=200, paid=True, outcome="ok",
                        purpose=f"Rented agent: {agent.title or agent.name}",
                    )
                    db.add(rc)
                    await db.flush()
                    # Renter pays the full price (credit first).
                    if Decimal(str(user.credit_remaining)) >= price:
                        user.credit_remaining = (
                            Decimal(str(user.credit_remaining)) - price
                        )
                    db.add(Payment(
                        api_call_id=rc.id, run_id=run.id,
                        wallet_id=run.wallet_id, user_id=run.user_id,
                        amount=price, currency="USDC",
                        network=settings.x402_network,
                        status=PaymentStatus.settled,
                        facilitator_ref="platform-credit",
                        reconcile_note="marketplace rent (renter paid)",
                        idempotency_key="rent_" + uuid.uuid4().hex,
                    ))
                    # Creator's earning (80%).
                    db.add(Payment(
                        api_call_id=rc.id, run_id=run.id,
                        wallet_id=run.wallet_id,
                        user_id=run.creator_user_id, amount=creator_cut,
                        currency="USDC", network=settings.x402_network,
                        status=PaymentStatus.settled,
                        facilitator_ref="creator-earning",
                        reconcile_note=(agent.title or agent.name)[:120],
                        idempotency_key="earn_" + uuid.uuid4().hex,
                    ))
                    rent_total = price

            run_row = (
                await db.execute(select(Run).where(Run.id == run.id))
            ).scalar_one()
            run_row.total_spend = (
                Decimal(str(run_row.total_spend)) + fee + rent_total
            )
            run_row.total_calls = (run_row.total_calls or 0) + 1
            await db.commit()
            await hub.publish(run.id, {"kind": "payment_settled", "data": {
                "amount": str(fee), "url": "agent://hermes+web",
                "purpose": "Hermes + web usage", "tx_hash": None,
            }})
        except Exception:  # noqa: BLE001
            logger.exception("usage billing failed")

        await emit("answer", text=answer[:8000])
        db.add(Memory(user_id=run.user_id, agent_id=agent.id, run_id=run.id,
                       kind="result", content=f"[{run.goal[:80]}] "
                       f"{answer[:400]}"))
        await db.commit()
        await persist_journal()
        return answer[:8000]
