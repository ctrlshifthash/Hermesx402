import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Download } from "lucide-react";
import { api, wsUrl } from "@/lib/api";
import type { Run, RunEvent } from "@/lib/types";
import { StatusBadge, Spinner } from "@/components/ui";
import Markdown from "@/components/Markdown";
import PaymentApprover from "@/components/PaymentApprover";
import { usd, dur } from "@/lib/format";
import { useToasts } from "@/lib/store";
import { useAuth } from "@/lib/auth";

const MARK: Record<string, string> = {
  reasoning: "REASON",
  api_call_started: "CALL",
  payment_required: "402",
  payment_sign_request: "APPROVE",
  payment_blocked: "BLOCKED",
  payment_settled: "SETTLED",
  payment_failed: "FAILED",
  api_call_error: "ERROR",
  api_call_done: "DONE",
  status: "STATUS",
  answer: "ANSWER",
};
const TONE: Record<string, string> = {
  answer: "text-ink font-semibold",
  payment_settled: "text-credit",
  payment_blocked: "text-debit",
  payment_failed: "text-debit",
  api_call_error: "text-debit",
  payment_required: "text-ink-700",
  status: "text-accent",
};

function line(e: RunEvent): string {
  const d = e.data || {};
  switch (e.kind) {
    case "reasoning": return d.text;
    case "answer": return d.text;
    case "api_call_started": return `${d.url} — ${d.purpose}`;
    case "payment_required": return `Payment required — ${d.amount} ${d.currency}`;
    case "payment_sign_request": return "Trial credit used up — approve this payment in your wallet";
    case "payment_blocked": return `Blocked (${d.reason}, cap ${d.cap}) — $0 moved`;
    case "payment_settled":
      return (
        `Paid ${usd(d.amount)} USDC → ${d.url} · ` +
        (d.tx_hash
          ? `tx ${String(d.tx_hash).slice(0, 16)}…`
          : "trial credit")
      );
    case "payment_failed": return `Payment failed (${d.amount}) — ${d.reason ?? ""}`;
    case "api_call_error": return `Request error: ${d.error}`;
    case "api_call_done": return `Completed (${d.status})`;
    case "status": return `Run ${d.status}`;
    default: return e.kind;
  }
}

export default function RunDetail() {
  const { id } = useParams();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [live, setLive] = useState(false);
  const push = useToasts((s) => s.push);
  const { wsAuthParams, mode } = useAuth();
  const bottom = useRef<HTMLDivElement>(null);
  const seeded = useRef(false);

  const { data: run, refetch } = useQuery({
    queryKey: ["run", id],
    queryFn: async () => (await api.get<Run>(`/runs/${id}`)).data,
    refetchInterval: (q) =>
      ["running", "queued"].includes((q.state.data as Run)?.status) ? 2500 : false,
  });

  // Seed the full conversation from the persisted journal (survives restarts
  // / opening the run late). WS then streams live updates for active runs.
  useEffect(() => {
    if (seeded.current || !run?.journal) return;
    try {
      const j = JSON.parse(run.journal);
      // Only seed if we have nothing live yet (don't clobber a live stream).
      if (Array.isArray(j) && j.length) {
        seeded.current = true;
        setEvents((cur) => (cur.length ? cur : j));
      }
    } catch {
      /* ignore */
    }
  }, [run]);

  const terminal =
    !!run && ["done", "failed", "stopped"].includes(run.status);

  useEffect(() => {
    if (!id || terminal) return; // finished runs: journal is the source
    let ws: WebSocket | null = null;
    let closed = false;
    (async () => {
      const params = await wsAuthParams();
      if (closed) return;
      ws = new WebSocket(wsUrl(`/runs/${id}/stream`, params));
      ws.onopen = () => setLive(true);
      ws.onclose = () => setLive(false);
      ws.onmessage = (m) => {
        const e: RunEvent = JSON.parse(m.data);
        if (e.kind === "ping") return;
        setEvents((p) => [...p, e]);
        if (e.kind === "payment_settled")
          push(`Posted ${usd(e.data?.amount)} USDC`, "ok");
        if (e.kind === "payment_blocked")
          push("Payment blocked by budget", "err");
        if (e.kind === "status") refetch();
      };
    })();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [id, terminal]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const spend =
    events
      .filter((e) => e.kind === "payment_settled")
      .reduce((s, e) => s + Number(e.data?.amount || 0), 0) ||
    Number(run?.total_spend || 0);

  const stop = async () => {
    await api.post(`/runs/${id}/stop`);
    push("Stop requested", "info");
  };

  const exportReport = () => {
    if (!run) return;
    const L = (e: RunEvent) => `- **${MARK[e.kind] ?? e.kind}** — ${line(e)}`;
    const md = [
      `# Hermesx402 run report`,
      ``,
      `**Run:** ${run.id}`,
      `**Goal:** ${run.goal}`,
      `**Status:** ${run.status}`,
      `**Spend:** ${usd(spend)} USDC · **Calls:** ${run.total_calls}`,
      `**Started:** ${run.started_at ?? "—"} · **Ended:** ${run.ended_at ?? "—"}`,
      ``,
      `## Journal (append-only)`,
      ``,
      ...events.filter((e) => e.kind !== "answer").map(L),
      ``,
      `## Answer`,
      ``,
      events.find((e) => e.kind === "answer")?.data?.text ||
        run.summary ||
        "_(none)_",
      ``,
      `---`,
      `_Generated by Hermesx402 — append-only ledger._`,
    ].join("\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `hermesx402-run-${run.id.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
    push("Report downloaded", "ok");
  };

  if (!run)
    return (
      <div className="flex h-64 items-center justify-center text-ink-500">
        <Spinner />
      </div>
    );

  const active = ["running", "queued"].includes(run.status);

  const signReq = [...events]
    .reverse()
    .find((e) => e.kind === "payment_sign_request");

  return (
    <div>
      {mode === "privy" && signReq?.data?.token && (
        <PaymentApprover
          runId={id as string}
          token={signReq.data.token}
          messageB64={signReq.data.message_b64}
        />
      )}
      <Link
        to="/runs"
        className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-500 hover:text-accent"
      >
        <ArrowLeft className="h-4 w-4" /> Run register
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4 border-b-2 border-rule pb-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.25em] text-ink-500">
            Run folio · {id?.slice(0, 8)}
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight">
            {run.goal}
          </h2>
          <div className="mt-2 flex items-center gap-3">
            <StatusBadge s={run.status} />
            <span className="text-[11px] uppercase tracking-wider text-ink-500">
              {dur(run.started_at, run.ended_at)} ·{" "}
              {live ? (
                <span className="text-credit">stream open</span>
              ) : (
                <span className="text-ink-300">stream closed</span>
              )}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost inline-flex items-center gap-1.5"
            onClick={exportReport}
            title="Download this run as a Markdown report"
          >
            <Download className="h-4 w-4" /> Export
          </button>
          {active && (
            <button className="btn-ghost text-debit" onClick={stop}>
              ■ Stop run
            </button>
          )}
        </div>
      </div>

      <div className="mt-px grid grid-cols-3 border border-rule">
        {[
          ["Live spend", usd(spend), "text-debit"],
          ["Calls", String(run.total_calls), "text-ink"],
          [
            "Settled",
            String(events.filter((e) => e.kind === "payment_settled").length),
            "text-credit",
          ],
        ].map(([k, v, c], i) => (
          <div key={k} className={`px-5 py-4 ${i < 2 ? "border-r border-rule" : ""}`}>
            <div className="text-[10px] uppercase tracking-widest text-ink-500">
              {k}
            </div>
            <motion.div
              key={v}
              initial={{ opacity: 0.5 }}
              animate={{ opacity: 1 }}
              className={`tnum mt-1 font-display text-2xl font-bold ${c}`}
            >
              {v}
            </motion.div>
          </div>
        ))}
      </div>

      <div className="mt-px border border-rule">
        <div className="border-b-2 border-rule px-5 py-2.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
          Run journal — append-only
        </div>
        <div className="max-h-[26rem] overflow-y-auto">
          {events.length === 0 ? (
            <p className="py-12 text-center text-[11px] uppercase tracking-widest text-ink-500">
              {active ? (
                <>
                  Awaiting entries
                  <span className="animate-blink">_</span>
                </>
              ) : (
                "No entries recorded"
              )}
            </p>
          ) : (
            events.map((e, i) =>
              e.kind === "answer" ? (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="border-b border-rule/30 bg-paper-100"
                >
                  <div className="flex items-center gap-4 px-5 pt-3">
                    <span className="tnum w-10 shrink-0 text-[10px] uppercase tracking-wider text-ink-300">
                      {String(i + 1).padStart(3, "0")}
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-ink">
                      Answer
                    </span>
                  </div>
                  <div className="px-5 pb-4 pl-[3.75rem]">
                    <Markdown>{e.data?.text || ""}</Markdown>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-4 border-b border-rule/30 px-5 py-2 text-[13px]"
                >
                  <span className="tnum w-10 shrink-0 text-[10px] uppercase tracking-wider text-ink-300">
                    {String(i + 1).padStart(3, "0")}
                  </span>
                  <span
                    className={`w-20 shrink-0 text-[10px] font-semibold uppercase tracking-wider ${
                      TONE[e.kind] ?? "text-ink-500"
                    }`}
                  >
                    {MARK[e.kind] ?? e.kind}
                  </span>
                  <span className={TONE[e.kind] ?? "text-ink-700"}>
                    {line(e)}
                  </span>
                </motion.div>
              )
            )
          )}
          {active &&
            events.length > 0 &&
            !events.some((e) => e.kind === "answer") && (
              <div className="flex items-center gap-4 border-b border-rule/30 bg-paper-100 px-5 py-3 text-[13px]">
                <span className="tnum w-10 shrink-0 text-[10px] uppercase tracking-wider text-ink-300">
                  •••
                </span>
                <span className="w-20 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-accent">
                  Writing
                </span>
                <span className="text-ink-700">
                  Hermes is composing the answer
                  <span className="animate-blink">▍</span>
                  <span className="ml-2 inline-flex gap-1 align-middle">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent" />
                  </span>
                </span>
              </div>
            )}
          <div ref={bottom} />
        </div>
      </div>

      {run.summary && (
        <div className="mt-px border border-rule bg-paper-100 p-5">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
            Closing entry
          </p>
          <Markdown>{run.summary}</Markdown>
        </div>
      )}
    </div>
  );
}
