import { create } from "zustand";
import { api, setActiveWalletId } from "./api";
import type { Wallet } from "./types";

/* Toasts */
type Toast = { id: number; msg: string; kind: "ok" | "err" | "info" };
interface ToastState {
  toasts: Toast[];
  push: (msg: string, kind?: Toast["kind"]) => void;
  drop: (id: number) => void;
}
export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push: (msg, kind = "info") =>
    set((s) => {
      const id = Date.now() + Math.random();
      setTimeout(() => s.drop(id), 4200);
      return { toasts: [...s.toasts, { id, msg, kind }] };
    }),
  drop: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/* Wallets — a user has many; one is "active" and scopes every API call. */
interface WalletState {
  wallets: Wallet[];
  activeId: string | null;
  loaded: boolean;
  load: () => Promise<void>;
  setActive: (id: string) => void;
  add: (address: string, label: string, network?: string) => Promise<Wallet>;
  setPrimary: (id: string) => Promise<void>;
  rename: (id: string, label: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  reset: () => void;
}

const LS = "al_active_wallet";

export const useWallets = create<WalletState>((set, get) => ({
  wallets: [],
  activeId: localStorage.getItem(LS),
  loaded: false,
  load: async () => {
    const { data } = await api.get<Wallet[]>("/wallets");
    let active = get().activeId;
    if (!active || !data.find((w) => w.id === active))
      active = data[0]?.id ?? null;
    setActiveWalletId(active);
    if (active) localStorage.setItem(LS, active);
    set({ wallets: data, activeId: active, loaded: true });
  },
  setActive: (id) => {
    setActiveWalletId(id);
    localStorage.setItem(LS, id);
    set({ activeId: id });
  },
  add: async (address, label, network = "eip155:8453") => {
    try {
      const { data } = await api.post<Wallet>("/wallets", {
        address,
        label,
        network,
      });
      set((s) => ({ wallets: [...s.wallets, data] }));
      if (!get().activeId) get().setActive(data.id);
      return data;
    } catch (e: any) {
      // Already linked (409) is not an error — reconcile to the existing row.
      if (e?.response?.status === 409) {
        const { data } = await api.get<Wallet[]>("/wallets");
        set({ wallets: data });
        const ex = data.find(
          (w) => w.address.toLowerCase() === address.toLowerCase()
        );
        if (ex) {
          if (!get().activeId) get().setActive(ex.id);
          return ex;
        }
      }
      throw e;
    }
  },
  setPrimary: async (id) => {
    await api.post(`/wallets/${id}/primary`);
    await get().load();
  },
  rename: async (id, label) => {
    await api.post(`/wallets/${id}/rename`, { label });
    await get().load();
  },
  remove: async (id) => {
    await api.delete(`/wallets/${id}`);
    const rest = get().wallets.filter((w) => w.id !== id);
    set({ wallets: rest });
    if (get().activeId === id) {
      const next = rest[0]?.id ?? null;
      setActiveWalletId(next);
      if (next) localStorage.setItem(LS, next);
      else localStorage.removeItem(LS);
      set({ activeId: next });
    }
  },
  reset: () => {
    setActiveWalletId(null);
    localStorage.removeItem(LS);
    set({ wallets: [], activeId: null, loaded: false });
  },
}));
