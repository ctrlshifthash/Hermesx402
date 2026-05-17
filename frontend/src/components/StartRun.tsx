import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { useToasts } from "@/lib/store";
import { Spinner } from "@/components/ui";
import { usd } from "@/lib/format";
import type { Agent, Run } from "@/lib/types";

const PRESETS = [
  "Compare the best LLM API providers for production in 2026 (price per 1M tokens, context window, one strength + one weakness each), then recommend one for a cost-sensitive startup.",
  "Research the best value GPUs for AI inference under $500 right now — compare 3, with current prices and VRAM, and pick one.",
  "Give me a sourced brief on the state of the x402 payment protocol in 2026: who's building on it, real adoption, and open risks.",
  "Find the top 3 self-custody Solana wallets in 2026, compare security and UX, and recommend one for a non-technical user.",
];

export default function StartRun() {
  const [open, setOpen] = useState(false);
  const [goal, setGoal] = useState(PRESETS[0]);
  const [busy, setBusy] = useState(false);
  const push = useToasts((s) => s.push);
  const nav = useNavigate();
  const qc = useQueryClient();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await api.get("/auth/me")).data,
    enabled: open,
  });
  const { data: health } = useQuery({
    queryKey: ["healthz"],
    queryFn: async () => (await api.get("/healthz")).data,
    enabled: open,
    staleTime: 60000,
  });
  const fee = Number(health?.pricing?.run_fee_usd ?? 0);
  const credit = Number(me?.credit_remaining ?? 0);
  const runsLeft = fee > 0 ? Math.floor(credit / fee) : null;

  const launch = async () => {
    setBusy(true);
    try {
      let agents = (await api.get<Agent[]>("/agents")).data;
      if (agents.length === 0)
        agents = [
          (
            await api.post<Agent>("/agents", {
              name: "Research Scout",
              config_json: '{"runner": "hermes"}',
            })
          ).data,
        ];
      const run = (
        await api.post<Run>("/runs", { agent_id: agents[0].id, goal })
      ).data;
      push("Run filed", "ok");
      qc.invalidateQueries({ queryKey: ["runs"] });
      setOpen(false);
      nav(`/runs/${run.id}`);
    } catch (e: any) {
      push(e?.response?.data?.detail ?? "Failed to start run", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button className="btn-primary" onClick={() => setOpen(true)}>
        + New run
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-5"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          >
            <motion.div
              className="card w-full max-w-lg p-0"
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b-2 border-rule px-5 py-3">
                <h3 className="font-display text-lg font-bold uppercase tracking-wide">
                  File a new run
                </h3>
                <button onClick={() => setOpen(false)}>
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="p-5">
                <label className="label">Goal / instruction</label>
                <textarea
                  className="input h-24 resize-none"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {PRESETS.map((p) => (
                    <button
                      key={p}
                      onClick={() => setGoal(p)}
                      className="border border-rule bg-paper-100 px-2.5 py-1 text-[11px] uppercase tracking-wide hover:bg-paper-200"
                    >
                      {p}
                    </button>
                  ))}
                </div>
                <div className="mt-5 flex items-center justify-between border border-rule bg-paper-100 px-4 py-2.5 text-[11px] uppercase tracking-wider">
                  <span className="text-ink-500">
                    Est. cost{" "}
                    <span className="tnum font-semibold text-ink">
                      ≈ {usd(fee)}
                    </span>{" "}
                    / run
                  </span>
                  <span className="text-ink-500">
                    Credit{" "}
                    <span className="tnum font-semibold text-credit">
                      {usd(credit)}
                    </span>
                    {runsLeft !== null && (
                      <span className="text-ink-300">
                        {" "}
                        · ~{runsLeft} left
                      </span>
                    )}
                  </span>
                </div>
                {runsLeft === 0 && (
                  <p className="mt-2 text-[11px] uppercase tracking-wider text-debit">
                    Trial credit exhausted — connect & fund a Solana wallet to
                    keep running.
                  </p>
                )}
                <button
                  className="btn-primary mt-4 w-full"
                  onClick={launch}
                  disabled={busy || goal.trim().length < 3}
                >
                  {busy ? <Spinner /> : "Launch run →"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
