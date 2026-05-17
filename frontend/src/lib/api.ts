import axios from "axios";

export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

export const api = axios.create({ baseURL: `${API_BASE}/api` });

// Auth + wallet are injected by the app shell (Privy token or dev id, plus the
// active wallet). Kept as setters so non-React modules stay decoupled.
let tokenProvider: () => Promise<string | null> = async () => null;
let devUser: string | null = null;
let guestId: string | null = null;
let activeWalletId: string | null = null;

export function setTokenProvider(fn: () => Promise<string | null>) {
  tokenProvider = fn;
}
export function setDevUser(id: string | null) {
  devUser = id;
}
export function setGuestId(id: string | null) {
  guestId = id;
}
export function setActiveWalletId(id: string | null) {
  activeWalletId = id;
}

api.interceptors.request.use(async (cfg) => {
  const token = await tokenProvider();
  cfg.headers = cfg.headers ?? {};
  // Signed-in token wins; otherwise a frictionless guest identity; dev last.
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  else if (guestId) cfg.headers["X-Guest-Id"] = guestId;
  else if (devUser) cfg.headers["X-Dev-User"] = devUser;
  if (activeWalletId) cfg.headers["X-Wallet-Id"] = activeWalletId;
  return cfg;
});

export function wsUrl(path: string, params: Record<string, string> = {}) {
  const u = new URL(API_BASE);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  const qs = new URLSearchParams(params).toString();
  return `${u.origin}/api${path}${qs ? `?${qs}` : ""}`;
}
