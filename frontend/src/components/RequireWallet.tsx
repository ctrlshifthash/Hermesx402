import { ReactNode } from "react";
import { Wallet } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useWallets } from "@/lib/store";
import { Spinner } from "@/components/ui";

/* Inline gate — same page, same nav. No redirect: the ledger just shows a
   "connect to populate" state, then fills in place once a wallet is live. */

function Panel({
  title,
  hint,
  cta,
}: {
  title: string;
  hint: string;
  cta: ReactNode;
}) {
  return (
    <div className="mx-auto mt-10 max-w-md border border-rule bg-paper-100 p-8 text-center shadow-hard">
      <div className="mx-auto mb-5 grid h-14 w-14 place-items-center border border-rule bg-paper-200">
        <Wallet className="h-6 w-6" />
      </div>
      <h2 className="font-display text-xl font-bold">{title}</h2>
      <p className="mx-auto mt-2 max-w-xs text-sm text-ink-500">{hint}</p>
      <div className="mt-6 flex justify-center">{cta}</div>
    </div>
  );
}

export default function RequireWallet({ children }: { children: ReactNode }) {
  const { ready, authenticated, connect, mode } = useAuth();
  const { wallets, loaded } = useWallets();

  if (!ready)
    return (
      <div className="grid h-64 place-items-center text-ink-500">
        <Spinner />
      </div>
    );

  if (!authenticated)
    return (
      <Panel
        title="Sign in to start — $1 free"
        hint="Email or wallet, no crypto needed. You instantly get $1 of free credit and a working ledger. A wallet is only needed later to fund beyond the free credit."
        cta={
          <button className="btn-primary" onClick={connect}>
            {mode === "dev" ? "Enter the demo" : "Sign in — get $1 free"}
          </button>
        }
      />
    );

  // Authenticated users always have a default wallet auto-provisioned, so
  // there is no separate "link a wallet" wall before using the free credit.

  return <>{children}</>;
}
