import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Play, Pause, Trash2, Clock } from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, Schedule } from "@/lib/types";
import { useWallets, useToasts } from "@/lib/store";
import { Card, Skeleton, EmptyState, Spinner } from "@/components/ui";
import { ago } from "@/lib/format";

const INTERVALS = [
  ["Every 5 min", 300],
  ["Every 30 min", 1800],
  ["Hourly", 3600],
  ["Every 6 h", 21600],
  ["Daily", 86400],
] as const;

function every(s: number): string {
  const m = INTERVALS.find(([, v]) => v === s);
  return m ? m[0] : `Every ${Math.round(s / 60)} min`;
}

type Row = Schedule & { _walletId: string; _walletLabel: string };

export default function Schedules() {
  const qc = useQueryClient();
  const push = useToasts((s) => s.push);
  const { wallets } = useWallets();

  const [open, setOpen] = useState(false);
  const [walletId, setWalletId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [goal, setGoal] = useState(
    "Use the Hermesx402 premium data API for GPU prices + benchmarks, then recommend the best GPU under $500."
  );
  const [interval, setInterval] = useState(3600);
  const [busy, setBusy] = useState(false);

  // schedules across ALL wallets (not just the active one)
  const { data: rows, isLoading } = useQuery({
    queryKey: ["schedules-all", wallets.map((w) => w.id)],
    enabled: wallets.length > 0,
    refetchInterval: 5000,
    queryFn: async (): Promise<Row[]> => {
      const lists = await Promise.all(
        wallets.map(async (w) => {
          const r = await api.get<Schedule[]>(
            `/schedules?wallet_id=${w.id}`
          );
          return r.data.map((s) => ({
            ...s,
            _walletId: w.id,
            _walletLabel: w.label,
          }));
        })
      );
      return lists.flat();
    },
  });

  // agents for the wallet chosen in the modal
  const selWallet = walletId || wallets[0]?.id || "";
  const { data: agents } = useQuery({
    queryKey: ["agents", selWallet],
    enabled: !!selWallet && open,
    queryFn: async () =>
      (await api.get<Agent[]>(`/agents?wallet_id=${selWallet}`)).data,
  });
  useEffect(() => {
    if (agents && agents.length && !agents.find((a) => a.id === agentId))
      setAgentId(agents[0].id);
  }, [agents]); // eslint-disable-line

  const create = async () => {
    if (!selWallet) return push("Link a wallet first", "err");
    if (!agentId)
      return push("This wallet has no agents — create one in Agents", "err");
    setBusy(true);
    try {
      await api.post(`/schedules?wallet_id=${selWallet}`, {
        agent_id: agentId,
        goal,
        interval_seconds: interval,
      });
      qc.invalidateQueries({ queryKey: ["schedules-all"] });
      push("Schedule created", "ok");
      setOpen(false);
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Failed", "err");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (r: Row) => {
    await api.post(`/schedules/${r.id}/toggle?wallet_id=${r._walletId}`);
    qc.invalidateQueries({ queryKey: ["schedules-all"] });
  };
  const del = async (r: Row) => {
    if (!window.confirm("Delete this schedule?")) return;
    await api.delete(`/schedules/${r.id}?wallet_id=${r._walletId}`);
    qc.invalidateQueries({ queryKey: ["schedules-all"] });
    push("Schedule deleted", "ok");
  };

  return (
    <div>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-2 border-rule pb-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
            Unattended recurring runs · all wallets
          </div>
          <h2 className="font-display text-3xl font-bold tracking-tight">
            Schedules
          </h2>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" /> New schedule
        </button>
      </div>

      <p className="mb-px border border-rule bg-paper-100 px-4 py-2 text-[12px] text-ink-700">
        Each scheduled run is budget- and credit-enforced — autonomous
        recurring spend is hard-capped.
      </p>

      {isLoading ? (
        <Skeleton className="h-48" />
      ) : !rows || rows.length === 0 ? (
        <EmptyState
          title="No schedules"
          hint="Create one to have an agent run unattended on a recurring basis."
          icon={<Clock className="h-8 w-8" />}
        />
      ) : (
        <Card className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b-2 border-rule text-left text-[10px] uppercase tracking-widest text-ink-500">
                <th className="px-5 py-3 font-semibold">Goal</th>
                <th className="px-3 py-3 font-semibold">Wallet</th>
                <th className="px-3 py-3 font-semibold">Every</th>
                <th className="px-3 py-3 font-semibold">State</th>
                <th className="px-3 py-3 text-right font-semibold">Fired</th>
                <th className="px-3 py-3 text-right font-semibold">Last</th>
                <th className="px-5 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s, i) => (
                <tr key={s.id} className={i ? "border-t border-rule/40" : ""}>
                  <td className="max-w-[20rem] truncate px-5 py-3">
                    {s.goal}
                  </td>
                  <td className="px-3 py-3 text-ink-700">{s._walletLabel}</td>
                  <td className="px-3 py-3 text-ink-700">
                    {every(s.interval_seconds)}
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={`border px-2 py-0.5 text-[11px] uppercase tracking-wider ${
                        s.active
                          ? "border-credit text-credit"
                          : "border-ink-500 text-ink-500"
                      }`}
                    >
                      {s.active ? "active" : "paused"}
                    </span>
                  </td>
                  <td className="tnum px-3 py-3 text-right">{s.runs_fired}</td>
                  <td className="px-3 py-3 text-right text-[11px] uppercase tracking-wider text-ink-500">
                    {s.last_run_at ? ago(s.last_run_at) : "—"}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => toggle(s)}
                        title={s.active ? "Pause" : "Resume"}
                        className="border border-rule p-1.5 hover:bg-paper-200"
                      >
                        {s.active ? (
                          <Pause className="h-3.5 w-3.5" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => del(s)}
                        title="Delete"
                        className="border border-rule p-1.5 text-debit hover:bg-paper-200"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {open && (
        <div
          className="fixed inset-0 z-[60] grid place-items-center bg-ink/40 p-5"
          onClick={() => setOpen(false)}
        >
          <div
            className="card w-full max-w-lg p-0"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b-2 border-rule px-5 py-3 font-display text-lg font-bold uppercase tracking-wide">
              New schedule
            </div>
            <div className="p-5">
              <label className="label">Wallet (pays for the runs)</label>
              <select
                className="input"
                value={selWallet}
                onChange={(e) => {
                  setWalletId(e.target.value);
                  setAgentId("");
                }}
              >
                {wallets.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.label} {w.is_primary ? "★" : ""}
                  </option>
                ))}
              </select>

              <label className="label mt-4">Agent (on that wallet)</label>
              {agents && agents.length === 0 ? (
                <div className="border border-rule bg-paper-200 px-3 py-2 text-[12px] text-ink-700">
                  No agents on this wallet. Create one in the Agents tab, or
                  pick another wallet.
                </div>
              ) : (
                <select
                  className="input"
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                >
                  {(agents ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              )}

              <label className="label mt-4">Goal</label>
              <textarea
                className="input h-24 resize-none"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              />
              <label className="label mt-4">Run every</label>
              <select
                className="input"
                value={interval}
                onChange={(e) => setInterval(Number(e.target.value))}
              >
                {INTERVALS.map(([lbl, v]) => (
                  <option key={v} value={v}>
                    {lbl}
                  </option>
                ))}
              </select>
              <button
                className="btn-primary mt-5 w-full"
                onClick={create}
                disabled={
                  busy ||
                  goal.trim().length < 3 ||
                  !agents ||
                  agents.length === 0
                }
              >
                {busy ? <Spinner /> : "Create schedule"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
