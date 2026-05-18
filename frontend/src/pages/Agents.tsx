import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Wallet as WalletIcon, Bot, Star, Pencil, Trash2, Store } from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, Wallet } from "@/lib/types";
import { useWallets, useToasts } from "@/lib/store";
import { useAuth } from "@/lib/auth";
import { Spinner, EmptyState } from "@/components/ui";
import { usd, ago } from "@/lib/format";

/* Agents tab = your connected wallets. Each wallet is an independent
   spending account; create as many agents under it as you want. */

function NewAgent({ walletId }: { walletId: string }) {
  const qc = useQueryClient();
  const push = useToasts((s) => s.push);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex gap-2 border-t border-rule bg-paper px-4 py-3">
      <input
        className="input"
        placeholder="New agent name (e.g. GPU Scout)…"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <button
        className="btn-primary shrink-0"
        disabled={busy || name.trim().length < 1}
        onClick={async () => {
          setBusy(true);
          try {
            await api.post(
              `/agents?wallet_id=${walletId}`,
              { name: name.trim(), config_json: '{"runner": "hermes"}' }
            );
            qc.invalidateQueries({ queryKey: ["agents", walletId] });
            setName("");
            push("Agent created", "ok");
          } catch (e: any) {
            push(e?.response?.data?.detail ?? "Failed", "err");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? <Spinner /> : <><Plus className="h-4 w-4" /> Create</>}
      </button>
    </div>
  );
}

function PublishModal({
  agent,
  walletId,
  onClose,
}: {
  agent: Agent;
  walletId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const push = useToasts((s) => s.push);
  const [title, setTitle] = useState(agent.title || agent.name);
  const [desc, setDesc] = useState(agent.description || "");
  const [cat, setCat] = useState(agent.category || "General");
  const [price, setPrice] = useState(
    agent.price_per_run_usd ? String(Number(agent.price_per_run_usd)) : "0.05"
  );
  const [busy, setBusy] = useState(false);

  const save = async (makePublic: boolean) => {
    setBusy(true);
    try {
      await api.post(`/agents/${agent.id}/publish?wallet_id=${walletId}`, {
        is_public: makePublic,
        title: title.trim(),
        description: desc.trim(),
        category: cat,
        price_per_run_usd: Number(price) || 0,
      });
      qc.invalidateQueries({ queryKey: ["agents", walletId] });
      qc.invalidateQueries({ queryKey: ["marketplace"] });
      push(makePublic ? "Agent listed on marketplace" : "Agent unlisted", "ok");
      onClose();
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Failed", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-center bg-ink/40 p-5"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-md p-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b-2 border-rule px-5 py-3 font-display text-lg font-bold uppercase tracking-wide">
          List “{agent.name}” on the marketplace
        </div>
        <div className="p-5">
          <label className="label">Title</label>
          <input
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <label className="label mt-3">Description</label>
          <textarea
            className="input h-20 resize-none"
            placeholder="What does this agent do well?"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
          />
          <div className="mt-3 flex gap-3">
            <div className="flex-1">
              <label className="label">Category</label>
              <select
                className="input"
                value={cat}
                onChange={(e) => setCat(e.target.value)}
              >
                {["General", "Research", "Finance", "Crypto", "Dev", "Data"].map(
                  (c) => (
                    <option key={c}>{c}</option>
                  )
                )}
              </select>
            </div>
            <div className="w-32">
              <label className="label">Price/run $</label>
              <input
                className="input tnum"
                type="number"
                min="0"
                step="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </div>
          </div>
          <p className="mt-3 text-[11px] uppercase tracking-wider text-ink-500">
            You earn 80% of each rental; renters also pay their own usage.
          </p>
          {(title.trim().length < 1 || desc.trim().length < 1) && (
            <p className="mt-2 text-[11px] uppercase tracking-wider text-debit">
              Add a title and a short description to publish.
            </p>
          )}
          <div className="mt-4 flex gap-2">
            <button
              className="btn-primary flex-1"
              disabled={
                busy || title.trim().length < 1 || desc.trim().length < 1
              }
              onClick={() => save(true)}
            >
              {busy ? <Spinner /> : "Publish"}
            </button>
            {agent.is_public && (
              <button
                className="btn-ghost text-debit"
                disabled={busy}
                onClick={() => save(false)}
              >
                Unlist
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function WalletCard({ wallet }: { wallet: Wallet }) {
  const qc = useQueryClient();
  const push = useToasts((s) => s.push);
  const setPrimary = useWallets((s) => s.setPrimary);
  const renameWallet = useWallets((s) => s.rename);
  const [pub, setPub] = useState<Agent | null>(null);
  const { data: agents, isLoading } = useQuery({
    queryKey: ["agents", wallet.id],
    queryFn: async () =>
      (await api.get<Agent[]>(`/agents?wallet_id=${wallet.id}`)).data,
  });

  const rename = async (a: Agent) => {
    const name = window.prompt("Rename agent", a.name)?.trim();
    if (!name || name === a.name) return;
    try {
      await api.put(`/agents/${a.id}?wallet_id=${wallet.id}`, {
        name,
        config_json: a.config_json,
      });
      qc.invalidateQueries({ queryKey: ["agents", wallet.id] });
      push("Agent renamed", "ok");
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Rename failed", "err");
    }
  };

  const remove = async (a: Agent) => {
    if (!window.confirm(`Delete agent "${a.name}"? This cannot be undone.`))
      return;
    try {
      await api.delete(`/agents/${a.id}?wallet_id=${wallet.id}`);
      qc.invalidateQueries({ queryKey: ["agents", wallet.id] });
      push("Agent deleted", "ok");
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Delete failed", "err");
    }
  };
  return (
    <div className="border border-rule bg-paper-100">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-rule px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center border border-rule bg-paper-200">
            <WalletIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 font-display text-lg font-bold">
              {wallet.label}
              <button
                title="Rename wallet"
                onClick={async () => {
                  const name = window
                    .prompt("Rename wallet", wallet.label)
                    ?.trim();
                  if (!name || name === wallet.label) return;
                  try {
                    await renameWallet(wallet.id, name);
                    push("Wallet renamed", "ok");
                  } catch (e: any) {
                    push(e?.response?.data?.detail ?? "Rename failed", "err");
                  }
                }}
                className="border border-rule p-1 text-ink-500 hover:text-accent"
              >
                <Pencil className="h-3 w-3" />
              </button>
              {wallet.is_primary ? (
                <span className="inline-flex items-center gap-1 border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-accent">
                  <Star className="h-3 w-3" /> Primary
                </span>
              ) : (
                <button
                  onClick={async () => {
                    try {
                      await setPrimary(wallet.id);
                      push("Set as primary", "ok");
                    } catch (e: any) {
                      push(e?.response?.data?.detail ?? "Failed", "err");
                    }
                  }}
                  className="border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-ink-500 hover:text-accent"
                >
                  Make primary
                </button>
              )}
            </div>
            <div className="tnum text-[11px] text-ink-500">
              {wallet.address} · {wallet.network}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-widest text-ink-500">
            Balance
          </div>
          <div className="tnum text-lg font-bold text-credit">
            {usd(wallet.balance_cached)}
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="p-5">
          <Spinner />
        </div>
      ) : agents && agents.length > 0 ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-[10px] uppercase tracking-widest text-ink-500">
              <th className="px-5 py-2 font-semibold">Agent</th>
              <th className="px-3 py-2 font-semibold">Runner</th>
              <th className="px-3 py-2 font-semibold">Created</th>
              <th className="px-5 py-2 text-right font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a, i) => {
              // Empty/!scripted config runs the real Hermes LLM (the backend
              // default when a model key is set). Only show "scripted" when
              // it was explicitly chosen.
              let runner = "hermes";
              try {
                const r = JSON.parse(a.config_json || "{}").runner;
                runner = r === "scripted" ? "scripted" : "hermes";
              } catch {}
              return (
                <tr
                  key={a.id}
                  className={i ? "border-t border-rule/40" : ""}
                >
                  <td className="px-5 py-3 font-semibold">
                    <span className="inline-flex items-center gap-2">
                      <Bot className="h-4 w-4 text-ink-500" /> {a.name}
                      {a.is_public && (
                        <span className="border border-credit/50 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-credit">
                          Listed
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="border border-rule px-2 py-0.5 text-[11px] uppercase tracking-wider">
                      {runner}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-[11px] uppercase tracking-wider text-ink-500">
                    {ago(a.created_at)}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setPub(a)}
                        title={a.is_public ? "Edit listing" : "List on marketplace"}
                        className={`border border-rule p-1.5 hover:bg-paper-200 ${
                          a.is_public ? "text-credit" : "text-ink-500"
                        }`}
                      >
                        <Store className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => rename(a)}
                        title="Rename"
                        className="border border-rule p-1.5 hover:bg-paper-200"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => remove(a)}
                        title="Delete"
                        className="border border-rule p-1.5 text-debit hover:bg-paper-200"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="px-5 py-6 text-center text-[12px] uppercase tracking-wider text-ink-500">
          No agents on this wallet yet
        </p>
      )}
      <NewAgent walletId={wallet.id} />
      {pub && (
        <PublishModal
          agent={pub}
          walletId={wallet.id}
          onClose={() => setPub(null)}
        />
      )}
    </div>
  );
}

export default function Agents() {
  const { wallets } = useWallets();
  const add = useWallets((s) => s.add);
  const push = useToasts((s) => s.push);
  const { mode, linkWallet } = useAuth();
  const [open, setOpen] = useState(false);
  const doLink = () => (mode === "privy" ? linkWallet() : setOpen(true));
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <div>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-2 border-rule pb-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
            Connected wallets & agents
          </div>
          <h2 className="font-display text-3xl font-bold tracking-tight">
            Agents
          </h2>
        </div>
        <button className="btn-primary" onClick={doLink}>
          <Plus className="h-4 w-4" /> Link a wallet
        </button>
      </div>

      {wallets.length === 0 ? (
        <EmptyState
          title="No wallets linked"
          hint="Link a wallet to create agents that spend from it."
        />
      ) : (
        <div className="space-y-px">
          {wallets.map((w) => (
            <WalletCard key={w.id} wallet={w} />
          ))}
        </div>
      )}

      {open && (
        <div
          className="fixed inset-0 z-[60] grid place-items-center bg-ink/40 p-5"
          onClick={() => setOpen(false)}
        >
          <div
            className="card w-full max-w-md p-0"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b-2 border-rule px-5 py-3 font-display text-lg font-bold uppercase tracking-wide">
              Link a wallet
            </div>
            <div className="p-5">
              <label className="label">Wallet address</label>
              <input
                className="input"
                placeholder="0x…"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
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
                    await add(address.trim(), label.trim() || "Wallet");
                    push("Wallet linked", "ok");
                    setOpen(false);
                    setAddress("");
                    setLabel("");
                  } catch (e: any) {
                    push(e?.response?.data?.detail ?? "Failed", "err");
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
      )}
    </div>
  );
}
