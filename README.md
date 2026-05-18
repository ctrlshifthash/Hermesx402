<div align="center">

# HERMES·x402

### Autonomous AI agents that pay for the data they need — on-chain, on the record.

A real [Nous Hermes](https://nousresearch.com/) agent researches the live web,
reasons over what it finds, and **pays x402 paywalls in USDC on Solana** — every
cent double-entered into an audit ledger you control, behind hard budgets that
stop spend *before* it leaves the wallet.

[**🌐 Website**](https://hermesx402.dev) ·
[**𝕏 / Twitter**](https://x.com/tryhermesx402) ·
[**🚀 Live app**](https://hermesx402.vercel.app) ·
[**API**](https://hermesx402-production.up.railway.app/api/healthz)

`FastAPI` · `React + Vite` · `x402` · `Solana mainnet` · `Privy` · `Nous Hermes 3 70B`

</div>

---

## The idea

The web is putting up paywalls for machines: HTTP **`402 Payment Required`** is
finally being used for what it was reserved for. The [x402
protocol](https://www.x402.org/) lets a client settle that payment in
stablecoin and retry — no accounts, no API keys, no invoices.

**Hermesx402** is the cockpit for that world. You give a real LLM agent a goal
and a budget. It does genuine research, and when it hits a priced endpoint it
pays the micropayment itself in USDC on Solana and keeps going. Nothing is
simulated: real model, real web, real on-chain settlement, real
explorer-verifiable transactions — all written into a tamper-evident,
double-entry ledger.

> **Honesty is the product.** Trial-credit spend that hasn't moved real money is
> labelled *"Trial credit"*, never a fake hash. Real settlements carry a real
> Solana tx hash you can open on Solscan. The agent never invents a fact or a
> source URL.

---

## How it works

```
  1. SIGN IN                2. RUN                       3. PAY                4. LEDGER
  ┌──────────┐   goal   ┌───────────────┐  402 +     ┌──────────────┐  tx   ┌────────────┐
  │  Privy   │ ───────► │ Nous Hermes   │  no creds  │  x402 client │ ────► │ append-only│
  │  wallet  │          │ • plan        │ ─────────► │  • budget ✓  │       │ double-    │
  │  connect │ ◄─────── │ • web research│            │  • USDC pay  │ ◄──── │ entry      │
  └──────────┘  answer  │ • synthesize  │  data      │  • Solana    │ recon │ ledger     │
                        └───────────────┘            └──────────────┘       └────────────┘
```

1. **Sign in** with Privy (wallet connect). Every account gets **$1 free
   credit** — no signup, no card.
2. **File a run.** Hermes plans, does **live web research** (real citations),
   and writes a structured, sourced answer.
3. **It pays its way.** If the goal needs a priced x402 endpoint, the agent
   settles the micropayment in **USDC on Solana mainnet** through a facilitator
   — *only after* the budget gate passes. Over budget = blocked, $0 moves.
4. **Who pays?** Trial credit first (platform-funded, debited as your tab).
   When it runs out, the agent pays from **your own wallet** — you approve the
   payment in your wallet at spend time. The server never holds your key.
5. **Everything is on the books.** Every call and payment is double-entered
   with amount, status, and a real tx hash, reconciled against settlement.

---

## Features

| | |
|---|---|
| 🧠 **Real Hermes reasoning** | Every run is driven by a real Nous Hermes 3 (70B) LLM — planning, reasoning, writing. Nothing scripted. |
| 🌐 **Live web research** | Searches the live web, answers with real, clickable citations. Never fabricates a URL or a fact. |
| 🪙 **Autonomous x402 payments** | Settles `402` paywalls in USDC on **Solana mainnet** over the x402 protocol — idempotent, on-chain, no human in the loop. |
| 🛡️ **Hard budget guardrails** | Per-transaction / per-run / per-day caps enforced **before** any signature. Over budget → blocked instantly. |
| 💳 **Credit → your wallet** | $1 free credit, then approve-at-spend from your own Privy/Solana wallet. Non-custodial — the server only ever gets a signature. |
| 📒 **Append-only ledger** | Double-entry calls + payments, reconciled, exportable to Markdown, real Solscan links. |
| 🔁 **Persistent memory** | Agents recall conclusions from past runs and build on them. |
| ⏱️ **Scheduled & unattended** | Recurring goals fire on a timer, under the same budget. |
| 🚧 **Anti-abuse** | One-time trial credit per IP; runs blocked when credit is exhausted without a funded wallet. |

---

## Architecture

```
  React + Vite ──REST──►  FastAPI  ──►  Run worker (in-proc / arq)
  Tailwind/Framer  ◄─WS─    │              └─► OpenRouterAgentRunner
  TanStack/Zustand          │                    │ Nous Hermes (OpenRouter)
        │                   │                    │ live web research
        │                   │                    └─► PaidHttpClient ── the x402 wrapper
        │                   │                          │ budget check (pre-pay)
        │                   │                          │ idempotent settle
        │                   │                          │ persist call + payment
        │                   │                          └─► PaymentProvider
        │                   │                                ├─ platform signer  (trial credit)
        │                   │                                ├─ Privy-delegated   (user wallet)
        │                   │                                └─ browser approve-at-spend
        │                   ▼
        └──────────  SQLite / Postgres  ◄─ SQLAlchemy 2 async · Alembic
                            ▲
                     x402 SDK + facilitator (payai · Solana mainnet)
```

**`app/x402/wrapper.py`** is the heart: request → parse `402` → **budget check
before any payment** → idempotently claim a payment row → settle exactly once →
persist one `api_call` + one `payment` → emit a live WS event. A crash between
claim and settle leaves a `pending` row flagged for reconciliation — never a
blind re-pay.

**`app/x402/provider.py`** isolates settlement behind one seam. The real
`X402PaymentProvider` uses the official x402 SDK + a facilitator; the signer is
swappable: the **platform key** (trial credit), a **Privy-delegated** user
wallet, or **browser approve-at-spend** — all the same `ClientSvmSigner`
interface.

---

## Tech stack

- **Backend:** FastAPI · async SQLAlchemy 2 · Pydantic v2 · Alembic · SQLite (local) / Postgres (prod)
- **Frontend:** React 18 · TypeScript · Vite · TailwindCSS · Framer Motion · TanStack Query · Zustand
- **Agent:** Nous Hermes 3 (70B) via OpenRouter + live web plugin
- **Payments:** x402 protocol · USDC · Solana mainnet · [payai](https://facilitator.payai.network) facilitator
- **Auth:** Privy wallet connect (JWKS ES256), frictionless guest sessions
- **Deploy:** Railway (backend) · Vercel (frontend)

---

## Quick start (local)

**Backend** — zero-config (SQLite, in-proc worker):
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate            # Windows  ·  source .venv/bin/activate (mac/linux)
pip install -r requirements.txt
cp .env.example .env                # then fill in your keys
uvicorn app.main:app --reload       # http://localhost:8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

Open the app, run a goal, watch the live journal stream. Tests:
```bash
cd backend && pytest -q             # critical-path suite
```

### Prove the money path is real
```bash
python -m scripts.verify_settlement   # one real on-chain x402 settlement → prints tx hash
python -m scripts.verify_user_pays    # credit exhausted → user wallet pays → service responds
```

---

## Deployment

**Backend → Railway.** Root directory `backend`, Dockerfile build. Set the env
vars from `.env.example` (Privy, OpenRouter, x402/Solana, `FRONTEND_ORIGIN`).
The app binds Railway's `$PORT` automatically.

**Frontend → Vercel.** Root directory `frontend`, Vite preset. Set
`VITE_API_BASE=https://<your-backend>.up.railway.app` and redeploy (Vite bakes
env at build time).

Then set the backend's `FRONTEND_ORIGIN` to the exact Vercel origin (no
trailing slash) for CORS. Secrets are documented in `backend/.env.example`;
never commit real `.env`.

---

## Project structure

```
backend/
  app/
    agent/        OpenRouterAgentRunner (real Hermes + web), memory, plan
    x402/         wrapper · provider · pending · browser/Privy signers
    api/           auth · runs · wallets · payments · calls · dashboard · ops
    workers/      in-proc run worker + scheduler
    models/       SQLAlchemy schema (users·wallets·agents·runs·payments·…)
  scripts/        verify_settlement · verify_user_pays · seed · smoke
frontend/
  src/
    pages/        Dashboard · Runs · RunDetail · Payments · Calls · …
    components/   Shell · StartRun · Markdown · PaymentApprover · ui
    lib/          api · auth (Privy) · store
```

---

## Honest status

| Area | State |
|---|---|
| Real Nous Hermes reasoning + live web research | ✅ Working |
| Real on-chain x402 USDC settlement on **Solana mainnet** | ✅ Working — explorer-verifiable tx hashes |
| Budget guardrails (pre-pay, concurrency-safe) | ✅ Working, tested |
| Idempotency / no double-pay / crash→reconcile flag | ✅ Working, tested |
| Trial credit → user-wallet approve-at-spend | ✅ Working (final wallet click is the user's) |
| Privy auth · guest sessions · anti-abuse | ✅ Working |
| Append-only ledger · live WS streaming · export | ✅ Working |
| Scheduled/unattended runs | ✅ Working — but can't pay past credit (no human to approve) |
| Facilitator | Public facilitators settle Solana **mainnet**; the legacy free one is devnet-only. Code is facilitator-agnostic. |

No mock is presented as real. Trial-credit accounting is labelled as such;
real settlements carry a real tx hash.

---

<div align="center">

**Hermesx402** — built on x402 · real Hermes agents · append-only ledger

</div>
