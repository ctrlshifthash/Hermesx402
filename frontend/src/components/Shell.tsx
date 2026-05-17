import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Plus, Check, X } from "lucide-react";
import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useWallets, useToasts } from "@/lib/store";
import { api } from "@/lib/api";
import { usd } from "@/lib/format";
import { Spinner } from "@/components/ui";

const NETWORKS = [
  { v: "eip155:8453", label: "Base (ETH)" },
  { v: "eip155:84532", label: "Base Sepolia (test)" },
  { v: "eip155:1", label: "Ethereum" },
  { v: "solana", label: "Solana (Phantom)" },
];

function SettlementBadge() {
  const { data } = useQuery({
    queryKey: ["healthz"],
    queryFn: async () => (await api.get("/healthz")).data,
    refetchInterval: 60000,
    staleTime: 60000,
  });
  const mode = data?.settlement?.mode;
  if (!mode) return null;
  const live = mode === "live";
  return (
    <span
      title={
        live
          ? "Real on-chain Solana USDC settlement is armed"
          : `Trial-credit accounting — no funds move (${
              data?.settlement?.reason ?? "no funded signer"
            })`
      }
      className={`inline-flex items-center gap-1.5 ${
        live ? "text-credit" : "text-ink-300"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          live ? "bg-credit" : "bg-ink-300"
        }`}
      />
      Settlement: {live ? "Live · Solana" : "Mock"}
    </span>
  );
}

function CreditBadge() {
  const { authenticated } = useAuth();
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await api.get("/auth/me")).data,
    enabled: authenticated,
    refetchInterval: 8000,
  });
  if (!authenticated || !data) return null;
  return (
    <div className="border border-rule bg-paper-100 px-3 py-1.5 text-center">
      <div className="text-[10px] uppercase tracking-widest text-ink-500">
        Free credit
      </div>
      <div className="tnum text-sm font-bold text-accent">
        {usd(data.credit_remaining)}
      </div>
    </div>
  );
}

/* ONE shell for the whole product — same masthead + nav on the landing page
   and every data page. Connecting a wallet just makes data appear in place;
   nothing is a separate gated app. */

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/agents", label: "Agents" },
  { to: "/runs", label: "Runs" },
  { to: "/schedules", label: "Schedules" },
  { to: "/payments", label: "Payments" },
  { to: "/calls", label: "API Calls" },
  { to: "/budgets", label: "Budgets" },
];

function AddWallet({ onClose }: { onClose: () => void }) {
  const add = useWallets((s) => s.add);
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [network, setNetwork] = useState(NETWORKS[0].v);
  const [busy, setBusy] = useState(false);
  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center bg-ink/40 p-5"
      onClick={onClose}
    >
      <div className="card w-full max-w-md p-0" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b-2 border-rule px-5 py-3">
          <h3 className="font-display text-lg font-bold uppercase tracking-wide">
            Link a wallet
          </h3>
          <button onClick={onClose}>
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-5">
          <label className="label">Wallet address</label>
          <input
            className="input"
            placeholder="0x…"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
          <label className="label mt-4">Network</label>
          <select
            className="input"
            value={network}
            onChange={(e) => setNetwork(e.target.value)}
          >
            {NETWORKS.map((n) => (
              <option key={n.v} value={n.v}>
                {n.label}
              </option>
            ))}
          </select>
          <label className="label mt-4">Label</label>
          <input
            className="input"
            placeholder="Treasury, Research Ops…"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <button
            className="btn-primary mt-5 w-full"
            disabled={busy || address.trim().length < 4}
            onClick={async () => {
              setBusy(true);
              try {
                await add(address.trim(), label.trim() || "Wallet", network);
                qc.invalidateQueries();
                push("Wallet linked", "ok");
                onClose();
              } catch (e: any) {
                push(e?.response?.data?.detail ?? "Failed to link", "err");
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? <Spinner /> : "Link wallet"}
          </button>
        </div>
      </div>
    </div>
  );
}

function WalletControl() {
  const { ready, authenticated, connect, disconnect, mode, isGuest,
    linkWallet } = useAuth();
  // Linking an extra wallet must go through Privy (proof of ownership).
  // Dev mode has no Privy → fall back to the manual form.
  const doLink = () => (mode === "privy" ? linkWallet() : setAdding(true));
  const { wallets, activeId, setActive, loaded } = useWallets();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const active = wallets.find((w) => w.id === activeId);

  if (!ready) return <Spinner />;

  if (!authenticated)
    return (
      <button className="btn-primary !px-4 !py-2 text-xs" onClick={connect}>
        {mode === "dev" ? "Enter demo" : "Sign in — $1 free"}
      </button>
    );

  if (loaded && wallets.length === 0)
    return (
      <>
        <button
          className="btn-primary !px-4 !py-2 text-xs"
          onClick={doLink}
        >
          <Plus className="h-3.5 w-3.5" /> Link wallet
        </button>
        {adding && <AddWallet onClose={() => setAdding(false)} />}
      </>
    );

  return (
    <div className="relative flex items-center gap-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-3 border border-rule bg-paper-100 px-3 py-1.5 hover:bg-paper-200"
      >
        <div className="text-left">
          <div className="text-[10px] uppercase tracking-widest text-ink-500">
            {active?.label ?? "Wallet"}
          </div>
          <div className="tnum text-sm font-semibold text-credit">
            {active ? usd(active.balance_cached) : "—"}
          </div>
        </div>
        <ChevronDown className="h-4 w-4" />
      </button>
      {isGuest ? (
        <button
          onClick={connect}
          className="border border-rule bg-accent px-2.5 py-2 text-[10px] font-semibold uppercase tracking-wider text-paper-100"
          title="Save your work across devices / fund beyond the free $1"
        >
          Sign in to save
        </button>
      ) : (
        <button
          onClick={async () => {
            await disconnect();
            useWallets.getState().reset();
          }}
          className="border border-rule px-2.5 py-2 text-[10px] font-semibold uppercase tracking-wider hover:text-debit"
        >
          Exit
        </button>
      )}
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-72 border border-rule bg-paper-100 shadow-hard">
            {wallets.map((w) => (
              <button
                key={w.id}
                onClick={() => {
                  setActive(w.id);
                  qc.invalidateQueries();
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between border-b border-rule/40 px-4 py-3 text-left hover:bg-paper-200"
              >
                <div>
                  <div className="text-sm font-semibold">{w.label}</div>
                  <div className="tnum text-[11px] text-ink-500">
                    {w.address.slice(0, 10)}… · {usd(w.balance_cached)}
                  </div>
                </div>
                {w.id === activeId && <Check className="h-4 w-4 text-accent" />}
              </button>
            ))}
            <button
              onClick={() => {
                setOpen(false);
                doLink();
              }}
              className="flex w-full items-center gap-2 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-accent hover:bg-paper-200"
            >
              <Plus className="h-4 w-4" /> Link a wallet
            </button>
          </div>
        </>
      )}
      {adding && <AddWallet onClose={() => setAdding(false)} />}
    </div>
  );
}

export default function Shell() {
  const { authenticated, address, connectedWallets } = useAuth();
  const load = useWallets((s) => s.load);
  const add = useWallets((s) => s.add);
  const setActive = useWallets((s) => s.setActive);
  const loaded = useWallets((s) => s.loaded);
  const wallets = useWallets((s) => s.wallets);
  const activeId = useWallets((s) => s.activeId);
  const triedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (authenticated && !loaded) load().catch(() => {});
  }, [authenticated, loaded, load]);

  // Every wallet connected on Privy auto-appears as a linked wallet (EVM +
  // Solana). No manual paste step. The first connected one becomes active.
  useEffect(() => {
    if (!authenticated || !loaded || connectedWallets.length === 0) return;
    const have = new Set(wallets.map((w) => w.address.toLowerCase()));
    let activated = false;
    connectedWallets.forEach((cw, i) => {
      const a = cw.address.toLowerCase();
      const existing = wallets.find((w) => w.address.toLowerCase() === a);
      if (existing) {
        if (i === 0 && address && a === address.toLowerCase() &&
            activeId !== existing.id && !activated) {
          setActive(existing.id);
          activated = true;
        }
        return;
      }
      if (have.has(a) || triedRef.current.has(a)) return;
      triedRef.current.add(a);
      add(cw.address, "My Wallet", cw.chain)
        .then((w) => {
          if (i === 0 && !activated) {
            setActive(w.id);
            activated = true;
          }
        })
        .catch(() => load().catch(() => {})); // reconcile if already linked
    });
  }, [
    authenticated, loaded, wallets, connectedWallets, address, activeId,
    add, setActive, load,
  ]);

  return (
    <div className="mx-auto min-h-screen w-full max-w-[1760px] px-4 md:px-8">
      <header className="border-x border-t border-rule bg-paper-100">
        <div className="flex items-center justify-between border-b border-rule px-6 py-2 text-[11px] uppercase tracking-[0.2em] text-ink-500">
          <span>No. 402 · Bearer Ledger</span>
          <span className="hidden sm:block">Autonomous Agent Payments</span>
          <span>Est. 2026</span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-rule px-6 py-4">
          <Link to="/" className="font-display text-3xl font-bold tracking-tight">
            HERMES<span className="text-accent">x402</span>
          </Link>
          <div className="flex flex-wrap items-center gap-5">
            <nav className="flex items-center gap-5 text-[12px] font-semibold uppercase tracking-wider">
              <Link to="/" className="hover:text-accent">Home</Link>
              <Link to="/#how" className="hover:text-accent">How it works</Link>
              <Link to="/#rates" className="hover:text-accent">Rates</Link>
            </nav>
            <CreditBadge />
            <WalletControl />
          </div>
        </div>
        <nav className="flex overflow-x-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                clsx(
                  "whitespace-nowrap border-r border-rule px-5 py-3 text-sm font-semibold uppercase tracking-wide transition",
                  isActive
                    ? "bg-accent text-paper-100"
                    : "bg-paper-100 text-ink hover:bg-paper-200"
                )
              }
            >
              {n.label}
            </NavLink>
          ))}
          <div className="hidden flex-1 border-b border-rule md:block" />
        </nav>
      </header>

      <main className="border-x border-b border-rule bg-paper px-6 py-8">
        <Outlet />
      </main>
      <div className="flex flex-wrap items-center justify-between gap-3 border-x border-b border-rule bg-paper-100 px-6 py-3 text-[11px] uppercase tracking-widest text-ink-300">
        <span>
          Hermesx402 · built on x402 · real Hermes agents · append-only ledger
        </span>
        <SettlementBadge />
      </div>
    </div>
  );
}
