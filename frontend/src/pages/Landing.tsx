import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  Check,
  ArrowRight,
  Brain,
  Globe,
  Coins,
  ShieldCheck,
  Database,
  Clock,
  Store,
  Copy,
} from "lucide-react";
import { Link } from "react-router-dom";
import DemoButton from "@/components/DemoButton";

/* Standalone landing page (route "/"). Owns its own masthead + footer. */

const ENTRIES = [
  ["09:41:02", "Hermes — reason", "GPU pricing needed to compare options", "", ""],
  ["09:41:03", "GET api.gpudata.io", "402 Payment Required", "", "PENDING"],
  ["09:41:03", "Budget check", "0.02 ≤ 0.50/tx · 0.02 ≤ 2.00/run", "", "PASS"],
  ["09:41:04", "x402 settle", "USDC · Solana mainnet", "-0.02", "SETTLED"],
  ["09:41:07", "Hermes — reason", "cross-checking second source", "", ""],
  ["09:41:08", "Budget check", "per-run cap reached", "", "BLOCKED"],
];

function LedgerTape() {
  const [n, setN] = useState(3);
  useEffect(() => {
    const i = setInterval(
      () => setN((x) => (x >= ENTRIES.length ? 3 : x + 1)),
      1500
    );
    return () => clearInterval(i);
  }, []);
  const total = ENTRIES.slice(0, n)
    .filter((e) => e[4] === "SETTLED")
    .reduce((s, e) => {
      const num = parseFloat(String(e[3]).replace(/[^0-9.]/g, ""));
      return s + (Number.isFinite(num) ? num : 0);
    }, 0);
  return (
    <div className="card-flat bg-paper-100 shadow-hard">
      <div className="flex items-center justify-between border-b-2 border-rule px-4 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.2em]">
          Run #00417 — research-best-gpus
        </span>
        <span className="text-[11px] uppercase tracking-widest text-credit">
          ● live
        </span>
      </div>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-rule text-left text-[10px] uppercase tracking-widest text-ink-500">
            <th className="px-4 py-1.5 font-semibold">Time</th>
            <th className="px-2 py-1.5 font-semibold">Event</th>
            <th className="px-2 py-1.5 font-semibold">Detail</th>
            <th className="px-2 py-1.5 text-right font-semibold">USDC</th>
            <th className="px-4 py-1.5 text-right font-semibold">Mark</th>
          </tr>
        </thead>
        <tbody>
          {ENTRIES.slice(0, n).map((e, i) => (
            <motion.tr
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="border-b border-rule/40"
            >
              <td className="tnum px-4 py-1.5 text-ink-500">{e[0]}</td>
              <td className="px-2 py-1.5 font-semibold">{e[1]}</td>
              <td className="px-2 py-1.5 text-ink-700">{e[2]}</td>
              <td className="tnum px-2 py-1.5 text-right text-debit">{e[3]}</td>
              <td
                className={`px-4 py-1.5 text-right text-[10px] font-semibold uppercase ${
                  e[4] === "SETTLED"
                    ? "text-credit"
                    : e[4] === "BLOCKED"
                      ? "text-debit"
                      : "text-ink-500"
                }`}
              >
                {e[4]}
              </td>
            </motion.tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-rule">
            <td colSpan={3} className="px-4 py-2 text-[11px] uppercase tracking-widest">
              Run total
            </td>
            <td className="tnum px-2 py-2 text-right font-bold text-debit">
              −{total.toFixed(2)}
            </td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// Token contract address — swap "TBA" for the real address at launch.
const CONTRACT_ADDRESS = "TBA";

// Socials. Swap PUMPFUN to the token page once it's live.
const X_URL = "https://x.com/tryhermesx402";
const GITHUB_URL = "https://github.com/tryHermesx402/Hermesx402";
const PUMPFUN_URL = "https://pump.fun";

const IconX = (
  <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);
const IconGitHub = (
  <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
    <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.5 11.5 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.91 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222 0 1.606-.014 2.898-.014 3.293 0 .322.216.694.825.576C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
  </svg>
);
const IconPump = (
  <img
    src="https://static.wixstatic.com/media/e2da02_248e6293fa024f6e9dd4130271bb14c3~mv2.png"
    alt="Pump.fun"
    className="h-5 w-5 object-contain"
  />
);

function SocialRail() {
  const items = [
    { label: "Pump.fun", href: PUMPFUN_URL, icon: IconPump },
    { label: "X / Twitter", href: X_URL, icon: IconX },
    { label: "GitHub", href: GITHUB_URL, icon: IconGitHub },
  ];
  return (
    <div className="fixed right-3 top-1/2 z-40 hidden -translate-y-1/2 flex-col gap-2.5 lg:flex">
      {items.map((s) => (
        <a
          key={s.label}
          href={s.href}
          target="_blank"
          rel="noopener noreferrer"
          title={s.label}
          aria-label={s.label}
          className="grid h-11 w-11 place-items-center border border-rule bg-paper-100 text-ink shadow-hard transition-all duration-150 hover:-translate-x-1 hover:-translate-y-1 hover:scale-110 hover:bg-accent hover:text-paper-100 hover:shadow-none"
        >
          {s.icon}
        </a>
      ))}
    </div>
  );
}

function CopyCA() {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(CONTRACT_ADDRESS);
    } catch {
      /* clipboard blocked — ignore */
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={copy}
      title="Copy contract address"
      className="hidden w-[60ch] max-w-[42vw] items-center justify-center gap-2 border border-rule bg-paper px-4 py-2 font-mono text-[12px] uppercase tracking-wider text-ink hover:bg-paper-200 lg:flex"
    >
      <span className="text-ink-500">CA:</span>
      <span className="truncate">{CONTRACT_ADDRESS}</span>
      {copied ? (
        <span className="shrink-0 text-credit">copied</span>
      ) : (
        <Copy className="h-3.5 w-3.5 shrink-0 text-ink-500" />
      )}
    </button>
  );
}

const FEATURES = [
  [
    Brain,
    "Real Hermes reasoning",
    "Every run is driven by a real Nous Hermes large language model — planning, reasoning and writing. Nothing scripted, nothing faked.",
  ],
  [
    Globe,
    "Live web research",
    "The agent searches the live web, reads current sources, and answers with real, clickable citations — it never invents a URL or a fact.",
  ],
  [
    Coins,
    "Autonomous x402 payments",
    "When an API answers 402 Payment Required, the agent settles it in USDC on Solana over the x402 protocol — idempotent, on-chain, no human in the loop.",
  ],
  [
    ShieldCheck,
    "Hard budget guardrails",
    "Per-transaction, per-run and per-day caps are checked before any payment is signed. Over budget = blocked instantly, $0 moved.",
  ],
  [
    Database,
    "Persistent memory",
    "Agents recall conclusions from past runs and build on them, so repeated work gets sharper instead of starting from zero each time.",
  ],
  [
    Clock,
    "Scheduled & unattended",
    "Hand an agent a recurring goal and an interval. It fires on its own, under the same budget, and files every run into the ledger.",
  ],
  [
    Store,
    "Agent marketplace",
    "Publish an agent and earn when others rent it. Renters pay the listing price in real USDC from their own wallet per run — creators keep 80%, fully on-chain.",
  ],
] as const;

export default function Landing() {
  return (
    <div className="mx-auto w-full max-w-[1760px] px-4 md:px-8">
      <SocialRail />
      {/* MARKETING NAV — landing keeps its own header + a Dashboard button */}
      <header className="border-x border-t border-rule bg-paper-100">
        <div className="flex items-center justify-between border-b border-rule px-6 py-2 text-[11px] uppercase tracking-[0.2em] text-ink-500">
          <span>No. 402 · Bearer Ledger</span>
          <span className="hidden sm:block">Autonomous Agent Payments</span>
          <span>Est. 2026</span>
        </div>
        <div className="relative flex flex-wrap items-center justify-between gap-4 px-6 py-4">
          <Link
            to="/"
            className="flex items-center gap-3 font-display text-3xl font-bold tracking-tight"
          >
            <img src="/logo.png" alt="" className="h-11 w-auto" />
            <span>
              HERMES<span className="text-accent">x402</span>
            </span>
          </Link>
          <div className="pointer-events-none absolute left-1/2 -translate-x-1/2">
            <div className="pointer-events-auto">
              <CopyCA />
            </div>
          </div>
          <nav className="flex items-center gap-5 text-[12px] font-semibold uppercase tracking-wider">
            <Link to="/" className="hover:text-accent">Home</Link>
            <a href="#what" className="hover:text-accent">Features</a>
            <a href="#how" className="hover:text-accent">How it works</a>
            <a href="#rates" className="hover:text-accent">Rates</a>
            <Link to="/dashboard" className="btn-primary !px-4 !py-2 text-xs">
              Dashboard <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      {/* HERO */}
      <section className="grid border-x border-rule lg:grid-cols-[1.1fr_1px_1fr]">
        <div className="px-8 py-14 md:py-20">
          <div className="eyebrow mb-6">
            Real Hermes agents · x402 · USDC on Solana
          </div>
          <h1 className="font-display text-[2.6rem] font-bold leading-[1.18] tracking-tight md:text-[3.4rem]">
            Your agents can
            <br />
            pay their own way —
            <br />
            <span className="mt-1 inline-block bg-accent px-2 py-0.5 leading-tight text-paper-100">
              on the record.
            </span>
          </h1>
          <p className="mt-7 max-w-xl text-[15px] leading-relaxed text-ink-700">
            Hermesx402 gives a real Nous Hermes agent a wallet and a goal. It
            researches the live web, reasons over what it finds, and pays
            x402-paywalled APIs in USDC on Solana — every cent double-entered
            into an audit ledger you control, behind hard caps that stop spend
            before it leaves the wallet.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <DemoButton />
            <Link to="/dashboard" className="btn-ghost">
              Open the dashboard <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <p className="mt-3 text-[12px] uppercase tracking-wider text-ink-500">
            $1 free credit · no signup · connect a Solana wallet to go beyond it
          </p>
          <dl className="mt-12 grid max-w-xl grid-cols-4 border border-rule">
            {[
              ["Free credit", "$1"],
              ["Settle", "x402"],
              ["Network", "Solana"],
              ["Audit", "100%"],
            ].map(([k, v], i) => (
              <div
                key={k}
                className={`px-4 py-4 ${i < 3 ? "border-r border-rule" : ""}`}
              >
                <dd className="font-display text-2xl font-bold">{v}</dd>
                <dt className="text-[10px] uppercase tracking-widest text-ink-500">
                  {k}
                </dt>
              </div>
            ))}
          </dl>
        </div>
        <div className="hidden bg-rule lg:block" />
        <div className="flex flex-col justify-center border-t border-rule px-8 py-14 md:py-20 lg:border-t-0">
          <LedgerTape />
          <p className="mt-4 text-center text-[11px] uppercase tracking-widest text-ink-500">
            A real run, double-entered as it happens
          </p>
        </div>
      </section>

      {/* WHAT — feature grid */}
      <section id="what" className="border-x border-t-2 border-rule bg-paper-100">
        <div className="border-b border-rule px-8 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
          § What the agent actually does
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([Icon, title, desc], i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: (i % 3) * 0.06 }}
              className="border-b border-r border-rule px-8 py-9"
            >
              <Icon className="h-7 w-7 text-accent" strokeWidth={1.75} />
              <p className="mt-4 font-display text-xl font-semibold">{title}</p>
              <p className="mt-2 text-sm leading-relaxed text-ink-700">
                {desc}
              </p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="border-x border-t-2 border-rule">
        <div className="border-b border-rule bg-paper-100 px-8 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
          § How the ledger works
        </div>
        <div className="grid md:grid-cols-3">
          {[
            ["01", "Connect & budget", "Connect a Solana wallet (or several). Cap per-transaction, per-run and per-day — enforced before any payment is signed. Start on $1 of free credit, no signup."],
            ["02", "File a run", "Give Hermes a goal. It plans, researches the live web, calls APIs and auto-pays x402 paywalls — blocked instantly if it would breach a cap."],
            ["03", "Read the books", "Every call and payment is double-entered with amount, tx hash and status, then reconciled against settlement. Nothing off the record."],
          ].map(([no, t, d], i) => (
            <motion.div
              key={no}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.07 }}
              className={`px-8 py-9 ${i < 2 ? "border-r border-rule" : ""} border-b border-rule md:border-b-0`}
            >
              <div className="font-display text-5xl font-bold text-paper-300">
                {no}
              </div>
              <p className="mt-4 font-display text-xl font-semibold">{t}</p>
              <p className="mt-2 text-sm leading-relaxed text-ink-700">{d}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* UNDER THE HOOD */}
      <section className="border-x border-t-2 border-rule bg-paper-100">
        <div className="border-b border-rule px-8 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
          § Under the hood
        </div>
        <div className="flex flex-wrap divide-x divide-rule/40">
          {[
            ["Reasoning", "Nous Hermes 3 · 70B"],
            ["Payments", "x402 protocol · USDC"],
            ["Settlement", "Solana mainnet"],
            ["Auth", "Privy wallet connect"],
            ["Ledger", "Append-only double-entry"],
            ["API", "FastAPI · async"],
          ].map(([k, v]) => (
            <div key={k} className="grow px-6 py-5">
              <div className="text-[10px] uppercase tracking-widest text-ink-500">
                {k}
              </div>
              <div className="mt-1 font-display text-sm font-semibold">
                {v}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* RATE SHEET */}
      <section id="rates" className="border-x border-t-2 border-rule">
        <div className="border-b border-rule bg-paper-100 px-8 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
          § Rate sheet
        </div>
        <div className="grid md:grid-cols-3">
          {[
            ["Free credit", "$1.00", "once", ["Every account, automatically", "No signup, no card", "Covers your first ~8 runs end to end"]],
            ["Per run", "$0.12", "per run", ["Real Hermes reasoning + live web research", "Debited from free credit first", "Then your connected Solana wallet"]],
            ["Per paid API", "from $0.01", "per call", ["x402 micropayment in USDC on Solana", "Only when the agent hits a paywall", "Never above your per-tx / run / day caps"]],
          ].map(([name, price, unit, feats]: any, i) => (
            <div
              key={name}
              className={`px-8 py-9 ${i < 2 ? "border-r border-rule" : ""} ${
                i === 1 ? "bg-paper-200" : "bg-paper-100"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <p className="font-display text-xl font-semibold">{name}</p>
                <p className="font-display text-2xl font-bold tnum">
                  {price}
                  <span className="ml-1 text-[11px] font-semibold uppercase tracking-widest text-ink-500">
                    {unit}
                  </span>
                </p>
              </div>
              <ul className="mt-5 space-y-2 text-sm">
                {feats.map((x: string) => (
                  <li key={x} className="flex items-center gap-2 text-ink-700">
                    <Check className="h-4 w-4 shrink-0 text-credit" /> {x}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-rule bg-paper px-8 py-4 text-center text-[12px] uppercase tracking-wider text-ink-500">
          No subscriptions · no card · you only ever spend what your agent
          spends, inside the caps you set
        </div>
      </section>

      {/* SIGN-OFF */}
      <section className="flex flex-col items-center gap-5 border-x border-t-2 border-rule bg-paper-100 px-8 py-16 text-center">
        <h3 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
          Give your agent a wallet and a leash.
        </h3>
        <p className="max-w-xl text-sm leading-relaxed text-ink-700">
          A real Hermes agent, a hard budget, and a ledger that records every
          cent. Start free — no signup, no card.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <DemoButton />
          <Link to="/dashboard" className="btn-ghost">
            Open the dashboard <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <footer className="flex flex-col items-center justify-between gap-3 border border-rule bg-paper px-6 py-5 text-[11px] uppercase tracking-widest text-ink-500 md:flex-row">
        <span>© 2026 Hermesx402 — append-only</span>
        <span>Built on x402 · Real Hermes agents · Live</span>
      </footer>
    </div>
  );
}
