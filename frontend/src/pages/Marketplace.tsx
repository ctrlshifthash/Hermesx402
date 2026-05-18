import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, X, Store, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import type { MarketplaceItem, Earnings, Run } from "@/lib/types";
import { Skeleton, EmptyState, ErrorState } from "@/components/ui";
import { usd } from "@/lib/format";
import { useToasts } from "@/lib/store";

const CATEGORIES = ["All", "General", "Research", "Finance", "Crypto", "Dev", "Data"];

function RentModal({
  item,
  onClose,
}: {
  item: MarketplaceItem;
  onClose: () => void;
}) {
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const push = useToasts((s) => s.push);
  const nav = useNavigate();
  const qc = useQueryClient();

  const run = async () => {
    setBusy(true);
    try {
      const r = (
        await api.post<Run>("/runs", { agent_id: item.id, goal })
      ).data;
      push("Run filed — renting agent", "ok");
      qc.invalidateQueries({ queryKey: ["runs"] });
      onClose();
      nav(`/runs/${r.id}`);
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Failed to start run", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="card w-full max-w-lg p-0"
        initial={{ y: 12, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b-2 border-rule px-5 py-3">
          <h3 className="font-display text-lg font-bold uppercase tracking-wide">
            Rent · {item.title || item.name}
          </h3>
          <button onClick={onClose}>
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-5">
          <p className="mb-3 text-sm text-ink-700">{item.description}</p>
          <label className="label">Goal / instruction</label>
          <textarea
            className="input h-24 resize-none"
            placeholder="What should this agent do for you?"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <div className="mt-4 border border-rule bg-paper-100 px-4 py-2.5 text-[11px] uppercase tracking-wider text-ink-500">
            <div className="flex items-center justify-between">
              <span>Rental price</span>
              <span className="tnum font-semibold text-ink">
                {usd(item.price_per_run_usd)} USDC
              </span>
            </div>
            <p className="mt-1.5 normal-case tracking-normal text-ink-500">
              Paid in <b>real USDC from your connected wallet</b> — your
              wallet will prompt you to approve it before the agent runs. No
              trial credit, no payment = no run.
            </p>
          </div>
          <button
            className="btn-primary mt-4 w-full"
            disabled={busy || goal.trim().length < 3}
            onClick={run}
          >
            {busy ? "Filing…" : "Rent & run →"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default function Marketplace() {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");
  const [sel, setSel] = useState<MarketplaceItem | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["marketplace", cat],
    queryFn: async () =>
      (
        await api.get<MarketplaceItem[]>("/marketplace", {
          params: { category: cat === "All" ? undefined : cat },
        })
      ).data,
  });
  const { data: earn } = useQuery({
    queryKey: ["earnings"],
    queryFn: async () => (await api.get<Earnings>("/marketplace/earnings")).data,
  });

  const rows = (data ?? []).filter(
    (m) =>
      !q ||
      (m.title ?? "").toLowerCase().includes(q.toLowerCase()) ||
      (m.description ?? "").toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-2 border-rule pb-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
            Folio 08 — Agent exchange
          </div>
          <h2 className="font-display text-3xl font-bold tracking-tight">
            Marketplace
          </h2>
        </div>
        {earn && (
          <div className="flex items-center gap-2 border border-rule bg-paper-100 px-4 py-2">
            <TrendingUp className="h-4 w-4 text-credit" />
            <div>
              <div className="text-[10px] uppercase tracking-widest text-ink-500">
                Your earnings · {earn.rented_runs} rentals
              </div>
              <div className="tnum text-sm font-bold text-credit">
                {usd(earn.total_earned_usd)}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mb-px flex flex-wrap items-center gap-3 border border-rule bg-paper-100 p-3">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-ink-500" />
          <input
            className="input w-64 pl-9"
            placeholder="Search agents…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`-ml-px border border-rule px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide first:ml-0 ${
                cat === c
                  ? "bg-accent text-paper-100"
                  : "bg-paper-100 hover:bg-paper-200"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <Skeleton className="h-64" />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No agents listed yet"
          hint="Publish one of your agents (Agents tab) to rent it out, or check back soon."
          icon={<Store className="h-7 w-7" />}
        />
      ) : (
        <div className="grid gap-px border border-rule md:grid-cols-2 lg:grid-cols-3">
          {rows.map((m) => (
            <div
              key={m.id}
              className="flex flex-col bg-paper-100 p-5 hover:bg-paper-200"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-display text-lg font-bold leading-tight">
                  {m.title || m.name}
                </h3>
                <span className="shrink-0 border border-rule px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
                  {m.category || "General"}
                </span>
              </div>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-ink-700">
                {m.description || "No description provided."}
              </p>
              <div className="mt-4 flex items-center justify-between border-t border-rule/40 pt-3">
                <div>
                  <div className="tnum text-lg font-bold text-accent">
                    {Number(m.price_per_run_usd) > 0
                      ? `${usd(m.price_per_run_usd)}/run`
                      : "Free"}
                  </div>
                  <div className="text-[10px] uppercase tracking-widest text-ink-500">
                    {m.runs_rented} rentals
                  </div>
                </div>
                <button
                  className="btn-primary !px-4 !py-2 text-xs"
                  onClick={() => setSel(m)}
                >
                  Rent & run
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <AnimatePresence>
        {sel && <RentModal item={sel} onClose={() => setSel(null)} />}
      </AnimatePresence>
    </div>
  );
}
