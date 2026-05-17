# AgentLedger — Mission Control + Expense Tracking for AI Agents

Launch autonomous agent **runs**. When an API answers `402 Payment Required`,
the agent pays the micropayment over **x402** (USDC) — **only if within budget**
— and continues. Every call and payment is logged with full context and shown
in a real-time dashboard.

> **Honesty first.** This repository is a complete, working **architectural
> spine** with the critical money path built fully and tested. It runs
> end-to-end today against a **mock x402 facilitator + mock paid API** (the
> spec explicitly permits this as a build stage). The flag-flip to real money,
> real Hermes, mainnet, soak/reconcile-on-chain is **scaffolded and
> documented, not finished** — see [Honest status](#honest-status) and
> [Path to real](#path-to-real-phase-2). Nothing real-money is hidden behind a
> mock that pretends to be real.

---

## Quick start

### A. Local, zero-config (SQLite, in-proc worker, mock payments)
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate     # Windows
#                       source .venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
python -m scripts.seed                                # demo user + agent
uvicorn app.main:app --reload                         # http://localhost:8000
```
```bash
cd frontend
npm install && npm run dev                            # http://localhost:5173
```
Sign in with the pre-filled **demo@agentledger.dev / demo12345**, click
**Start a run**, watch the live timeline pay mock x402 paywalls.

### B. One command (Docker: api + worker + Postgres + Redis + frontend)
```bash
cp .env.example .env
docker-compose up --build
# frontend http://localhost:5173 · api http://localhost:8000/docs
```
Postgres runs Alembic migrations + seed automatically on boot.

### Tests (critical path)
```bash
cd backend && pytest -q          # 15 tests: wrapper, budget, auth, e2e
python -m scripts.smoke          # live-server full-pipeline smoke
```

---

## Architecture

```
                       ┌─────────────────────────────────────────┐
  React/TS (Vite)  ───► │  FastAPI                                 │
  Tailwind/Framer       │   auth · agents · runs · payments ·      │
  TanStack/Zustand      │   calls · budgets · dashboard · ops      │
        ▲   ▲           │                                          │
        │   │ WS        │   Run worker (inproc | arq)              │
        │   └───────────┤      └─► AgentRunner ──► PaidHttpClient  │
        │ REST          │                            (the x402     │
        │               │                             WRAPPER)    │
        │               │            │      │      │               │
        │               │     budget │ idem │ log  │ events        │
        │               │     check  │ pay  │ DB   │ hub ──► WS    │
        │               │            ▼      ▼                      │
        │               │     PaymentProvider  ◄── feature flag    │
        │               │      mock │ x402(real SDK + facilitator) │
        │               └──────────────────┬───────────────────────┘
        │                                  ▼
        └────────  PostgreSQL  ◄──  SQLAlchemy 2 async / Alembic
```

- **`app/x402/wrapper.py`** — the heart. Implements the full §3 contract:
  request → parse 402 → **budget check before any payment** → idempotent
  settle → retry with proof → persist one `api_call` + one `payment` → emit WS
  event. Crash between claim and settle leaves a `pending` payment flagged for
  reconciliation (never blind re-pay).
- **`app/services/budget.py`** — caps enforced against `settled + pending`
  spend so concurrent runs cannot collectively overspend. Pure, no side
  effects, unit-tested.
- **`app/x402/provider.py`** — `MockPaymentProvider` (deterministic, no money)
  vs `X402PaymentProvider` (real Coinbase SDK + facilitator). One env var
  switches them; nothing else changes.
- **`app/agent/`** — `ScriptedAgentRunner` genuinely drives the real wrapper
  (only the *reasoning model* is scripted). `mcp_server.py` exposes
  `paid_http_request` as an **MCP tool** — the concrete plug-in point for real
  Hermes.

### Why MCP for Hermes (not an in-proc tool)
Hermes runs as its own CLI/process and natively connects to **MCP servers**.
MCP is its first-class, process-isolated extension boundary — it also keeps
the server-custodied signer out of the model process. The scripted runner
shares our process so it uses the in-proc `PaidHttpClient` directly (no IPC).
Both paths funnel through the **same** wrapper, so budget/idempotency/audit
guarantees are runner-independent.

### x402 / Hermes interface findings (build step 4)
- x402 Python SDK: `x402Client`/`x402ClientSync`, `ExactEvmScheme` +
  `EthAccountSigner(Account.from_key(...))`, `x402_requests` /
  `create_payment_payload`, `get_payment_settle_response()` for the tx hash,
  `HTTPFacilitatorClient(url=...)`, `max_amount` policy. SDK layout drifts by
  version → isolated entirely behind `PaymentProvider`.
- Hermes: CLI-first, 40+ tools, **MCP** for custom capabilities, subagents,
  RPC tool calls. Real run needs model creds + the MCP server → documented
  limitation, not wired locally.

---

## Data model
`users · wallets · agents · runs · api_calls · payments · budgets ·
audit_log`. Money is `NUMERIC(38,18)`. `payments.idempotency_key` is **unique**
(no double-pay). FKs and `created_at` indexed; composite indexes on
`(run_id,status)` / `(run_id,outcome)`. Alembic migration `0001_initial`;
SQLite auto-creates for the zero-config path.

## Security
- Budget enforced **before** settlement; over-budget funds never move
  (test: `test_over_budget_blocked_no_funds_move`).
- Strict per-user scoping on every REST route **and** the WebSocket.
- JWT in httpOnly cookies; bcrypt; access/refresh + silent refresh.
- Secrets only via env; structured logs **redact** key/token/password fields;
  no signer ever client-side.
- Rate limiting on auth + run creation.

---

## Honest status

| Area | State |
|---|---|
| Auth, per-user isolation, REST, dashboards | **Real, working, tested** |
| x402 wrapper: 402→budget→pay→log→retry→stream | **Real, working, tested** |
| Budget enforcement (per-tx/run/day, concurrency-safe) | **Real, working, tested** |
| Idempotency / no-double-pay, crash→reconcile flag | **Real, working, tested** |
| Live WS run timeline + dashboard | **Real, working** |
| Docker compose (api/worker/db/redis/frontend) | **Real, working** |
| Payment **settlement** | **Mocked** (`MockPaymentProvider`, deterministic, no funds) |
| Paid API | **Mocked** (`/mockapi`, real 402 + header gate; only settlement faked) |
| Hermes reasoning | **Scripted** runner (real wrapper, scripted plan); MCP server provided |
| Reconciliation | Real for mock; **on-chain verify is a documented stub** |
| arq cross-process realtime | WS hub is in-proc; multi-proc needs **Redis pub/sub** (stub) |
| Mainnet money / soak / alerting | **Not done** — see below |

## Path to real (Phase 2)

| # | Item | Concrete next step |
|---|---|---|
| R1 | Real Hermes | `pip install mcp`, run `python -m app.agent.mcp_server`, point a Hermes agent's MCP config at `paid_http_request`, set agent `config_json.runner="hermes"`. Wrapper unchanged. |
| R2 | Real x402 | Uncomment `x402`, `eth-account` in `requirements.txt`; `PAYMENT_PROVIDER=x402`; set `X402_EVM_PRIVATE_KEY` (server custody), `X402_FACILITATOR_URL`, `X402_ASSET_ADDRESS`. `X402PaymentProvider` is already implemented. |
| R3 | Funded wallets | Replace seeded demo address with real per-user/agent key custody (KMS/HSM); refresh `balance_cached` from chain. |
| R4 | Budget proven w/ real money | Same `check_budget` runs pre-settlement; add a mainnet low-cap test asserting an over-budget call leaves balance unchanged. |
| R5 | Reconciliation | Implement chain/facilitator lookup in `services/reconcile.py` (currently flags real payments as unverified rather than claiming OK). |
| R6 | Failure handling | Idempotency + pending-flag implemented; add chaos tests for facilitator timeout / partial settle / worker kill. |
| R7 | Observability | `/metrics` + structured logs exist; add Sentry + alert on wallet drain / anomalous spend. |
| R8 | Security review | Re-audit key custody + isolation under the real-money path before raising caps. |
| R9 | Load/soak | `RUN_MODE=arq` + Redis; **swap the in-proc `EventHub` for Redis pub/sub** so the worker's events reach API WS clients across processes. |
| R10 | Staged rollout | `PAYMENT_PROVIDER` flag already gates mock↔real: local(mock) → staging(testnet) → prod(mainnet, low caps). |

## Definition-of-done gap
Real Hermes + real USDC on Base mainnet, on-chain reconciliation, cross-process
realtime, alerting and soak testing are **not** complete. Everything required
to get there is scaffolded behind the documented seams above — no mock is
presented as real.
