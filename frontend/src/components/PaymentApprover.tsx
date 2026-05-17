import { useEffect, useRef } from "react";
import { useSignMessage } from "@privy-io/react-auth/solana";
import { api } from "@/lib/api";
import { useToasts } from "@/lib/store";

/**
 * Approve-at-spend. When trial credit is exhausted the server pauses and
 * emits `payment_sign_request`; we sign the exact bytes with the user's
 * connected Solana wallet (their wallet pops up) and return the signature so
 * the x402 payment settles on-chain and the run continues. The key never
 * leaves the user's wallet.
 *
 * Mounted only in Privy auth mode (uses a Privy Solana hook).
 */
function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
function bytesToB64(b: Uint8Array): string {
  let s = "";
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return btoa(s);
}

export default function PaymentApprover({
  runId,
  token,
  messageB64,
}: {
  runId: string;
  token: string;
  messageB64: string;
}) {
  const { signMessage } = useSignMessage();
  const push = useToasts((s) => s.push);
  const handled = useRef<string | null>(null);

  useEffect(() => {
    if (!token || handled.current === token) return;
    handled.current = token;
    (async () => {
      try {
        push("Approve the payment in your wallet…", "info");
        const res: any = await signMessage({
          message: b64ToBytes(messageB64),
        });
        // Privy returns { signature: Uint8Array } or a raw Uint8Array.
        const sig: Uint8Array =
          res?.signature instanceof Uint8Array
            ? res.signature
            : res instanceof Uint8Array
              ? res
              : new Uint8Array(res?.signature ?? res);
        await api.post(`/runs/${runId}/sign`, {
          token,
          signature_b64: bytesToB64(sig),
        });
        push("Payment approved", "ok");
      } catch (e: any) {
        await api
          .post(`/runs/${runId}/sign`, {
            token,
            error: e?.message?.slice(0, 120) || "rejected",
          })
          .catch(() => {});
        push("Payment declined", "err");
      }
    })();
  }, [token, messageB64, runId, signMessage, push]);

  return null;
}
