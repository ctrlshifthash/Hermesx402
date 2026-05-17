import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Budget } from "@/lib/types";
import { Spinner } from "@/components/ui";
import { useToasts, useWallets } from "@/lib/store";
import { usd } from "@/lib/format";

function Block({ no, title, children }: any) {
  return (
    <div className="border border-rule bg-paper-100">
      <div className="border-b-2 border-rule px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
        {no} · {title}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

export default function Settings() {
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const { data: budget } = useQuery({
    queryKey: ["budget"],
    queryFn: async () => (await api.get<Budget>("/budget")).data,
  });
  const { wallets, activeId } = useWallets();
  const wallet = wallets.find((w) => w.id === activeId);

  const [form, setForm] = useState<Budget>({
    daily_cap: "5",
    per_tx_cap: "0.5",
    per_run_cap: "2",
  });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (budget) setForm(budget);
  }, [budget]);

  const save = async () => {
    setBusy(true);
    try {
      await api.put("/budget", {
        daily_cap: Number(form.daily_cap),
        per_tx_cap: Number(form.per_tx_cap),
        per_run_cap: Number(form.per_run_cap),
      });
      qc.invalidateQueries({ queryKey: ["budget"] });
      push("Budget posted", "ok");
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Failed to save", "err");
    } finally {
      setBusy(false);
    }
  };

  const reconcile = async () => {
    const { data } = await api.post("/reconcile");
    push(
      `Reconciled ${data.checked} · matched ${data.matched} · flagged ${data.flagged}`,
      data.flagged ? "err" : "ok"
    );
    qc.invalidateQueries({ queryKey: ["payments"] });
  };

  if (!budget) return <Spinner />;

  return (
    <div className="max-w-3xl">
      <div className="mb-7 border-b-2 border-rule pb-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
          Folio 05 — Controls
        </div>
        <h2 className="font-display text-3xl font-bold tracking-tight">
          Budgets & Settings
        </h2>
      </div>

      <div className="space-y-px">
        <Block no="A" title="Spending guardrails">
          <p className="mb-4 text-sm text-ink-700">
            Enforced server-side <strong>before</strong> any payment leaves the
            wallet. Over-cap calls are blocked, not paid.
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            {(
              [
                ["per_tx_cap", "Per transaction"],
                ["per_run_cap", "Per run"],
                ["daily_cap", "Per day"],
              ] as const
            ).map(([k, label]) => (
              <div key={k}>
                <label className="label">{label} (USDC)</label>
                <input
                  className="input tnum"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form[k]}
                  onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                />
              </div>
            ))}
          </div>
          <button className="btn-primary mt-5" onClick={save} disabled={busy}>
            {busy ? <Spinner /> : "Post guardrails"}
          </button>
        </Block>

        <Block no="B" title="Wallet">
          <div className="text-sm">
            {[
              ["Address", wallet?.address],
              ["Network", wallet?.network],
            ].map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between gap-4 border-b border-rule/40 py-2.5"
              >
                <span className="text-[11px] uppercase tracking-wider text-ink-500">
                  {k}
                </span>
                <span className="tnum text-[12px]">{v}</span>
              </div>
            ))}
            <div className="flex justify-between py-2.5">
              <span className="text-[11px] uppercase tracking-wider text-ink-500">
                Cached balance
              </span>
              <span className="tnum font-bold text-credit">
                {wallet ? usd(wallet.balance_cached) : "—"}
              </span>
            </div>
          </div>
        </Block>

        <Block no="C" title="Reconciliation">
          <p className="mb-4 text-sm text-ink-700">
            Cross-check posted payments against settlement records and flag
            mismatches so the books are provably accurate.
          </p>
          <button className="btn-ghost" onClick={reconcile}>
            Run reconciliation
          </button>
        </Block>
      </div>
    </div>
  );
}
