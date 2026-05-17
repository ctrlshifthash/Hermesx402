import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Download, X, ExternalLink } from "lucide-react";
import { api, API_BASE } from "@/lib/api";
import type { Payment } from "@/lib/types";
import { StatusBadge, Skeleton, EmptyState, ErrorState } from "@/components/ui";
import { usd, ago, shortHash, explorerUrl } from "@/lib/format";

const FILTERS = ["all", "settled", "blocked_budget", "pending", "failed"];

export default function Payments() {
  const [f, setF] = useState("all");
  const [sel, setSel] = useState<Payment | null>(null);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["payments"],
    queryFn: async () => (await api.get<Payment[]>("/payments")).data,
    refetchInterval: 5000,
  });
  const rows = (data ?? []).filter((p) => f === "all" || p.status === f);

  return (
    <div>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-2 border-rule pb-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
            Folio 03 — Cash book
          </div>
          <h2 className="font-display text-3xl font-bold tracking-tight">
            Payments
          </h2>
        </div>
        <a href={`${API_BASE}/api/payments/export.csv`} className="btn-ghost">
          <Download className="h-4 w-4" /> Export CSV
        </a>
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
        <EmptyState title="No entries" hint="Payments post here as agents pay x402 paywalls." />
      ) : (
        <div className="overflow-x-auto border border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b-2 border-rule text-left text-[10px] uppercase tracking-widest text-ink-500">
                <th className="px-5 py-3 font-semibold">Debit (USDC)</th>
                <th className="px-3 py-3 font-semibold">Mark</th>
                <th className="px-3 py-3 font-semibold">Network</th>
                <th className="px-3 py-3 font-semibold">Tx</th>
                <th className="px-3 py-3 font-semibold">Recon.</th>
                <th className="px-5 py-3 text-right font-semibold">Posted</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p, i) => (
                <tr
                  key={p.id}
                  onClick={() => setSel(p)}
                  className={`cursor-pointer hover:bg-paper-200 ${
                    i ? "border-t border-rule/40" : ""
                  }`}
                >
                  <td className="tnum px-5 py-3 font-semibold text-debit">
                    −{usd(p.amount)}
                  </td>
                  <td className="px-3 py-3"><StatusBadge s={p.status} /></td>
                  <td className="px-3 py-3 text-ink-700">{p.network}</td>
                  <td className="tnum px-3 py-3 text-[12px] text-ink-500">
                    {p.tx_hash ? (
                      shortHash(p.tx_hash)
                    ) : p.facilitator_ref === "platform-credit" ? (
                      <span className="text-accent">Trial credit</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-3 text-[12px]">
                    {p.reconciled ? (
                      <span className="text-credit">✓ ok</span>
                    ) : (
                      <span className="text-ink-300">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right text-[11px] uppercase tracking-wider text-ink-500">
                    {ago(p.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AnimatePresence>
        {sel && (
          <motion.div
            className="fixed inset-0 z-50 flex justify-end bg-ink/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSel(null)}
          >
            <motion.div
              className="h-full w-full max-w-md overflow-y-auto border-l-2 border-rule bg-paper-100"
              initial={{ x: 420 }}
              animate={{ x: 0 }}
              exit={{ x: 420 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b-2 border-rule px-6 py-4">
                <h3 className="font-display text-lg font-bold uppercase tracking-wide">
                  Voucher
                </h3>
                <button onClick={() => setSel(null)}>
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="p-6 text-sm">
                {[
                  ["Amount", `−${usd(sel.amount)} ${sel.currency}`],
                  ["Mark", sel.status],
                  ["Network", sel.network],
                  ["Facilitator", sel.facilitator_ref ?? "—"],
                  ["Idempotency", "enforced — no double-pay"],
                  ["Posted", new Date(sel.created_at).toLocaleString()],
                  ["Reconciled", sel.reconciled ? "Yes" : "Not yet"],
                  ["Note", sel.reconcile_note ?? "—"],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    className="flex justify-between gap-4 border-b border-rule/40 py-2.5"
                  >
                    <span className="text-[11px] uppercase tracking-wider text-ink-500">
                      {k}
                    </span>
                    <span className="text-right">{v}</span>
                  </div>
                ))}
                <div className="mt-4">
                  <p className="mb-1 text-[11px] uppercase tracking-wider text-ink-500">
                    {sel.tx_hash ? "Transaction hash" : "Settlement"}
                  </p>
                  {sel.tx_hash ? (
                    <>
                      <p className="tnum break-all text-[12px]">
                        {sel.tx_hash}
                      </p>
                      <a
                        href={explorerUrl(sel.tx_hash)}
                        target="_blank"
                        className="mt-2 inline-flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wider text-accent"
                      >
                        View on explorer <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </>
                  ) : sel.facilitator_ref === "platform-credit" ? (
                    <p className="text-[12px] text-accent">
                      Paid from your $1 trial credit (platform-covered — not an
                      on-chain transaction).
                    </p>
                  ) : (
                    <p className="text-[12px] text-ink-500">—</p>
                  )}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
