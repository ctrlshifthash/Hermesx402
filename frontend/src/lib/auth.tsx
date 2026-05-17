import {
  createContext, useContext, useEffect, useMemo, useState, ReactNode,
} from "react";
import { PrivyProvider, usePrivy } from "@privy-io/react-auth";
import { api, setDevUser, setGuestId, setTokenProvider } from "./api";

// Solana is loaded LAZILY at runtime and is strictly optional: if anything in
// that dependency graph throws, the app still runs with EVM/MetaMask. It can
// never crash module init (that was the white-screen).
let SOLANA_ERR = "";

async function loadSolana(): Promise<any> {
  try {
    const m = await import("@privy-io/react-auth/solana");
    const c = m.toSolanaWalletConnectors();
    if (!c) SOLANA_ERR = "toSolanaWalletConnectors() returned empty";
    return c;
  } catch (e: any) {
    SOLANA_ERR = String(e?.stack || e?.message || e);
    console.error("Solana connectors FAILED:", e);
    return null;
  }
}

/* Auth strategy is decided by the backend (`/auth/config`):
   - privy: real wallet connect via Privy; access token → API bearer.
   - dev:   no Privy app configured — a local dev identity so the app still
            runs (matches the seeded `dev:local` user).
   The rest of the app only sees `useAuth()`; it never branches on the mode. */

interface AuthState {
  ready: boolean;
  authenticated: boolean;
  mode: "privy" | "dev" | "loading";
  connect: () => void;
  disconnect: () => void;
  label: string;
  address: string | null; // primary connected wallet address (compat)
  // every wallet linked on the Privy account, with its chain
  connectedWallets: { address: string; chain: string }[];
  linkWallet: () => void; // opens Privy to link an extra wallet (any chain)
  isGuest: boolean; // true = frictionless anon session, not signed in
  // WS can't send headers from the browser → identity goes as query params.
  wsAuthParams: () => Promise<Record<string, string>>;
}

const Ctx = createContext<AuthState>({
  ready: false,
  authenticated: false,
  mode: "loading",
  connect: () => {},
  disconnect: () => {},
  label: "",
  address: null,
  connectedWallets: [],
  linkWallet: () => {},
  isGuest: true,
  wsAuthParams: async () => ({}),
});

// Stable per-browser guest id so anyone can use the app with $1 instantly,
// no sign-in. Signing in later creates a separate persistent account.
function ensureGuestId(): string {
  let g = localStorage.getItem("al_guest");
  if (!g) {
    g =
      "g_" +
      (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)).replace(
        /-/g,
        ""
      );
    localStorage.setItem("al_guest", g);
  }
  return g;
}

export const useAuth = () => useContext(Ctx);
export const getSolanaErr = () => SOLANA_ERR;

function PrivyBridge({
  children,
  guest,
}: {
  children: ReactNode;
  guest: string;
}) {
  const p = usePrivy();
  useEffect(() => {
    setTokenProvider(async () => {
      try {
        return p.authenticated ? await p.getAccessToken() : null;
      } catch {
        return null;
      }
    });
  }, [p.authenticated]);

  const u = p.user as any;
  // Every wallet linked on the Privy account (EVM + Solana).
  const connectedWallets: { address: string; chain: string }[] = (
    u?.linkedAccounts ?? []
  )
    .filter((a: any) => a?.type === "wallet" && a?.address)
    .map((a: any) => ({
      address: a.address as string,
      chain: a.chainType === "solana" ? "solana:mainnet" : "eip155:8453",
    }));
  const walletAddr: string | null =
    u?.wallet?.address ?? connectedWallets[0]?.address ?? null;
  const value: AuthState = {
    ready: p.ready,
    // Usable immediately as a guest; Privy sign-in is an optional upgrade.
    authenticated: p.authenticated || !!guest,
    mode: "privy",
    connect: p.login,
    disconnect: p.logout,
    label: p.authenticated
      ? walletAddr ?? u?.email?.address ?? "account"
      : "Guest",
    address: walletAddr,
    connectedWallets,
    linkWallet: () => {
      try {
        (p as any).linkWallet?.();
      } catch {
        /* noop */
      }
    },
    isGuest: !p.authenticated,
    wsAuthParams: async (): Promise<Record<string, string>> => {
      try {
        const t = p.authenticated ? await p.getAccessToken() : null;
        return t ? { token: t } : { guest };
      } catch {
        return { guest };
      }
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function DevAuth({ children }: { children: ReactNode }) {
  const [on, setOn] = useState(() => {
    const v = localStorage.getItem("al_dev_connected") === "1";
    // Set identity synchronously so the very first /wallets request (fired
    // from a child effect before this component's effect) carries it.
    setTokenProvider(async () => null);
    setDevUser(v ? "local" : null);
    return v;
  });
  useEffect(() => {
    setTokenProvider(async () => null);
    setDevUser(on ? "local" : null);
  }, [on]);
  const value: AuthState = {
    ready: true,
    authenticated: on,
    mode: "dev",
    connect: () => {
      localStorage.setItem("al_dev_connected", "1");
      setDevUser("local"); // synchronous — no race with load()
      setOn(true);
    },
    disconnect: () => {
      localStorage.removeItem("al_dev_connected");
      setOn(false);
    },
    label: "dev sandbox",
    address: null,
    connectedWallets: [],
    linkWallet: () => {},
    isGuest: false,
    wsAuthParams: async () => ({ dev: "local" }),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<
    { mode: string; privy_app_id: string | null } | null
  >(null);
  // null = solana attempt not finished; otherwise connectors or null
  const [sol, setSol] = useState<any>("pending");
  const guest = useMemo(() => ensureGuestId(), []);
  useEffect(() => {
    setGuestId(guest); // frictionless identity from first paint
    api
      .get("/auth/config")
      .then((r) => setCfg(r.data))
      .catch(() => setCfg({ mode: "dev", privy_app_id: null }));
    loadSolana().then((c) => setSol(c)); // never throws
  }, [guest]);

  const usePrivyMode = useMemo(
    () => cfg?.mode === "privy" && !!cfg?.privy_app_id,
    [cfg]
  );

  if (!cfg || sol === "pending")
    return (
      <div className="grid min-h-screen place-items-center text-ink-500">
        loading…
      </div>
    );

  if (usePrivyMode) {
    return (
      <PrivyProvider
        appId={cfg.privy_app_id as string}
        config={{
          // Email OR wallet — no crypto wallet required to get an account
          // and the $1 free credit. Wallet is only to fund beyond trial.
          loginMethods: ["email", "wallet", "google"],
          appearance: {
            theme: "light",
            accentColor: "#1F2EE6",
            walletChainType: sol ? "ethereum-and-solana" : "ethereum-only",
          },
          ...(sol
            ? { externalWallets: { solana: { connectors: sol } } }
            : {}),
          // An embedded Solana wallet for everyone — that's the wallet the
          // agent pays from once trial credit runs out (delegated signing
          // works on embedded wallets, not external ones).
          embeddedWallets: {
            createOnLogin: "users-without-wallets",
            solana: { createOnLogin: "all-users" },
          },
        }}
      >
        <PrivyBridge guest={guest}>{children}</PrivyBridge>
      </PrivyProvider>
    );
  }
  return <DevAuth>{children}</DevAuth>;
}
