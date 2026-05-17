import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { StatusBadge, Skeleton, EmptyState, ErrorState } from "@/components/ui";
import { usd, ago, dur } from "@/lib/format";
import StartRun from "@/components/StartRun";

const FILTERS = ["all", "running", "queued", "done", "failed", "stopped"];

export default function Runs() {
  const [f, setF] = useState("all");
  const [q, setQ] = useState("");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["runs"],
    queryFn: async () => (await api.get<Run[]>("/runs")).data,
    refetchInterval: 4000,
  });

  const rows = (data ?? [])
    .filter((r) => f === "all" || r.status === f)
    .filter((r) => r.goal.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-2 border-rule pb-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
            Folio 02 — Run register
          </div>
          <h2 className="font-display text-3xl font-bold tracking-tight">Runs</h2>
        </div>
        <StartRun />
      </div>

      <div className="mb-px flex flex-wrap items-center gap-3 border border-rule bg-paper-100 p-3">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-ink-500" />
          <input
            className="input w-64 pl-9"
            placeholder="Search goals…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="flex">
          {FILTERS.map((x) => (
            <button
              key={x}
              onClick={() => setF(x)}
              className={`border border-rule px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide ${
                f === x ? "bg-accent text-paper-100" : "bg-paper-100 hover:bg-paper-200"
              } -ml-px first:ml-0`}
            >
              {x}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <Skeleton className="h-64" />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState title="No runs" hint="File your first agent run to post entries." />
      ) : (
        <div className="overflow-x-auto border border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b-2 border-rule text-left text-[10px] uppercase tracking-widest text-ink-500">
                <th className="px-5 py-3 font-semibold">Goal</th>
                <th className="px-3 py-3 font-semibold">Status</th>
                <th className="px-3 py-3 text-right font-semibold">Spend</th>
                <th className="px-3 py-3 text-right font-semibold">Calls</th>
                <th className="px-3 py-3 text-right font-semibold">Duration</th>
                <th className="px-5 py-3 text-right font-semibold">Filed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={r.id}
                  className={`hover:bg-paper-200 ${i ? "border-t border-rule/40" : ""}`}
                >
                  <td className="px-5 py-3">
                    <Link
                      to={`/runs/${r.id}`}
                      className="font-semibold hover:text-accent"
                    >
                      {r.goal}
                    </Link>
                  </td>
                  <td className="px-3 py-3"><StatusBadge s={r.status} /></td>
                  <td className="tnum px-3 py-3 text-right font-semibold text-debit">
                    {usd(r.total_spend)}
                  </td>
                  <td className="tnum px-3 py-3 text-right text-ink-700">
                    {r.total_calls}
                  </td>
                  <td className="tnum px-3 py-3 text-right text-ink-700">
                    {dur(r.started_at, r.ended_at)}
                  </td>
                  <td className="px-5 py-3 text-right text-[11px] uppercase tracking-wider text-ink-500">
                    {ago(r.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
