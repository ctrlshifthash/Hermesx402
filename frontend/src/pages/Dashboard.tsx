import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip,
  BarChart, Bar,
} from "recharts";
import { api } from "@/lib/api";
import type { Dashboard as D } from "@/lib/types";
import { Card, Skeleton, StatusBadge, EmptyState, ErrorState } from "@/components/ui";
import { usd, ago } from "@/lib/format";
import StartRun from "@/components/StartRun";

const TIP = {
  background: "#FBF8F0",
  border: "1px solid #1A1712",
  borderRadius: 0,
  fontFamily: "IBM Plex Mono",
  fontSize: 12,
};

function PageHead({ title, sub, children }: any) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-2 border-rule pb-4">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
          {sub}
        </div>
        <h2 className="font-display text-3xl font-bold tracking-tight">{title}</h2>
      </div>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<D>("/dashboard")).data,
    refetchInterval: 5000,
  });

  if (isError)
    return <ErrorState onRetry={() => refetch()} />;

  if (isLoading || !data)
    return (
      <div className="grid grid-cols-2 gap-px border border-rule md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );

  const kpis = [
    ["Total spend", usd(data.total_spend), "text-debit"],
    ["Runs filed", String(data.total_runs), "text-ink"],
    ["API calls", String(data.total_calls), "text-ink"],
    ["Blocked", String(data.blocked_calls), "text-debit"],
  ];

  return (
    <div>
      <PageHead title="Trial Balance" sub="Folio 01 — Dashboard">
        <StartRun />
      </PageHead>

      {/* KPI strip — like a ledger summary line */}
      <div className="grid grid-cols-2 border border-rule md:grid-cols-4">
        {kpis.map(([k, v, c], i) => (
          <div
            key={k as string}
            className={`px-5 py-5 ${i < 3 ? "border-r border-rule" : ""} ${
              i < 2 ? "border-b md:border-b-0 border-rule" : ""
            }`}
          >
            <div className="text-[10px] uppercase tracking-widest text-ink-500">
              {k}
            </div>
            <div className={`tnum mt-2 font-display text-3xl font-bold ${c}`}>
              {v}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-px grid border border-rule lg:grid-cols-[2fr_1fr]">
        <div className="border-b border-rule p-5 lg:border-b-0 lg:border-r">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
            Spend over time
          </p>
          {data.spend_over_time.length === 0 ? (
            <EmptyState title="No spend recorded" hint="File a run to post entries." />
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <AreaChart
                data={data.spend_over_time.map((p) => ({
                  d: p.bucket,
                  v: Number(p.amount),
                }))}
              >
                <XAxis dataKey="d" stroke="#1A1712" fontSize={11} />
                <YAxis stroke="#1A1712" fontSize={11} />
                <Tooltip contentStyle={TIP} />
                <Area
                  type="stepAfter"
                  dataKey="v"
                  stroke="#1F2EE6"
                  fill="#1F2EE6"
                  fillOpacity={0.12}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="p-5">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
            Spend by API
          </p>
          {data.spend_by_api.length === 0 ? (
            <EmptyState title="No payments" />
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart
                data={data.spend_by_api.map((a) => ({
                  name: a.name,
                  v: Number(a.amount),
                }))}
                layout="vertical"
              >
                <XAxis type="number" stroke="#1A1712" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke="#1A1712"
                  width={84}
                  fontSize={10}
                />
                <Tooltip contentStyle={TIP} />
                <Bar dataKey="v" fill="#1A1712" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="mt-px border border-rule">
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
            Recent runs
          </p>
          <Link
            to="/runs"
            className="text-[11px] font-semibold uppercase tracking-wider text-accent"
          >
            View all →
          </Link>
        </div>
        {data.recent_runs.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No runs yet" hint="File your first agent run." />
          </div>
        ) : (
          data.recent_runs.map((r, i) => (
            <Link
              key={r.id}
              to={`/runs/${r.id}`}
              className={`flex items-center justify-between px-5 py-3 hover:bg-paper-200 ${
                i ? "border-t border-rule/40" : ""
              }`}
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{r.goal}</p>
                <p className="text-[11px] uppercase tracking-wider text-ink-500">
                  {ago(r.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-5">
                <span className="tnum text-sm font-semibold text-debit">
                  {usd(r.total_spend)}
                </span>
                <StatusBadge s={r.status} />
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
