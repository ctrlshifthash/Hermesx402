import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiCall } from "@/lib/types";
import { StatusBadge, Skeleton, EmptyState, ErrorState } from "@/components/ui";
import { ago } from "@/lib/format";

const FILTERS = ["all", "ok", "blocked_budget", "error", "unpaid"];

export default function Calls() {
  const [f, setF] = useState("all");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["calls"],
    queryFn: async () => (await api.get<ApiCall[]>("/calls")).data,
    refetchInterval: 5000,
  });
  const rows = (data ?? []).filter((c) => f === "all" || c.outcome === f);

  return (
    <div>
      <div className="mb-7 border-b-2 border-rule pb-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
          Folio 04 — Call journal
        </div>
        <h2 className="font-display text-3xl font-bold tracking-tight">
          API Calls
        </h2>
      </div>

      <div className="mb-px flex border border-rule bg-paper-100">
        {FILTERS.map((x) => (
          <button
            key={x}
            onClick={() => setF(x)}
            className={`border-r border-rule px-4 py-2 text-[11px] font-semibold uppercase tracking-wide ${
              f === x ? "bg-accent text-paper-100" : "hover:bg-paper-200"
            }`}
          >
            {x.replace("_", " ")}
          </button>
        ))}
      </div>

      {isLoading ? (
        <Skeleton className="h-64" />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState title="No calls" hint="Calls post here as agents reach APIs." />
      ) : (
        <div className="overflow-x-auto border border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b-2 border-rule text-left text-[10px] uppercase tracking-widest text-ink-500">
                <th className="px-5 py-3 font-semibold">Endpoint</th>
                <th className="px-3 py-3 font-semibold">Purpose</th>
                <th className="px-3 py-3 font-semibold">Outcome</th>
                <th className="px-3 py-3 font-semibold">Paid</th>
                <th className="px-3 py-3 text-right font-semibold">Code</th>
                <th className="px-3 py-3 text-right font-semibold">Latency</th>
                <th className="px-5 py-3 text-right font-semibold">When</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr
                  key={c.id}
                  className={`hover:bg-paper-200 ${i ? "border-t border-rule/40" : ""}`}
                >
                  <td className="tnum max-w-[16rem] truncate px-5 py-3 text-[12px] text-ink-700">
                    {c.method} {c.url}
                  </td>
                  <td className="max-w-[14rem] truncate px-3 py-3">{c.purpose}</td>
                  <td className="px-3 py-3"><StatusBadge s={c.outcome} /></td>
                  <td className="px-3 py-3 text-[12px]">
                    {c.paid ? (
                      <span className="text-credit">yes</span>
                    ) : (
                      <span className="text-ink-300">no</span>
                    )}
                  </td>
                  <td className="tnum px-3 py-3 text-right text-ink-700">
                    {c.status_code ?? "—"}
                  </td>
                  <td className="tnum px-3 py-3 text-right text-ink-700">
                    {c.latency_ms != null ? `${c.latency_ms}ms` : "—"}
                  </td>
                  <td className="px-5 py-3 text-right text-[11px] uppercase tracking-wider text-ink-500">
                    {ago(c.created_at)}
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
