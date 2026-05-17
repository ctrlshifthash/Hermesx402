import { ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";
import clsx from "clsx";
import { useToasts } from "@/lib/store";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("card", className)}>{children}</div>;
}

// Ledger stamp: square, bordered, uppercase. Status = a stamped mark.
const STATUS: Record<string, string> = {
  running: "border-accent text-accent",
  queued: "border-ink-500 text-ink-500",
  done: "border-credit text-credit",
  settled: "border-credit text-credit",
  ok: "border-credit text-credit",
  failed: "border-debit text-debit",
  error: "border-debit text-debit",
  stopped: "border-ink-500 text-ink-500",
  blocked_budget: "border-debit text-debit",
  pending: "border-ink-700 text-ink-700",
  unpaid: "border-ink-300 text-ink-300",
};

export function StatusBadge({ s }: { s: string }) {
  const live = s === "running";
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider",
        STATUS[s] ?? "border-ink-500 text-ink-500"
      )}
    >
      {live && <span className="h-1.5 w-1.5 bg-accent animate-blink" />}
      {s.replace("_", " ")}
    </span>
  );
}

export function Spinner() {
  return <Loader2 className="h-4 w-4 animate-spin" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function EmptyState({ title, hint, icon }: { title: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center border border-dashed border-rule bg-paper-100 py-16 text-center">
      <div className="mb-3 text-ink-300">{icon}</div>
      <p className="font-display text-lg font-semibold">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm text-ink-500">{hint}</p>}
    </div>
  );
}

export function ErrorState({
  hint,
  onRetry,
}: {
  hint?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center border border-dashed border-debit/50 bg-paper-100 py-16 text-center">
      <p className="font-display text-lg font-semibold text-debit">
        Couldn’t load this ledger
      </p>
      <p className="mt-1 max-w-sm text-sm text-ink-500">
        {hint ?? "The server didn’t respond. Check your connection and retry."}
      </p>
      {onRetry && (
        <button className="btn-ghost mt-4" onClick={onRetry}>
          ↻ Retry
        </button>
      )}
    </div>
  );
}

export function Toaster() {
  const { toasts, drop } = useToasts();
  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 30 }}
            onClick={() => drop(t.id)}
            className={clsx(
              "card-flat flex cursor-pointer items-center gap-2 px-4 py-3 text-sm shadow-hard",
              t.kind === "ok" && "border-l-4 border-l-credit",
              t.kind === "err" && "border-l-4 border-l-debit",
              t.kind === "info" && "border-l-4 border-l-accent"
            )}
          >
            <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-ink-500">
              {t.kind === "ok" ? "OK" : t.kind === "err" ? "ERR" : "LOG"}
            </span>
            <span>{t.msg}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
