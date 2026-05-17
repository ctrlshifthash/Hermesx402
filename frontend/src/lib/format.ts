export const usd = (v: string | number) =>
  `$${Number(v).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })}`;

export const shortHash = (h?: string | null) =>
  h ? `${h.slice(0, 8)}…${h.slice(-6)}` : "—";

// Backend (SQLite) returns naive UTC timestamps with no timezone. JS would
// parse those as LOCAL time → durations off by the UTC offset (the "60.0M"
// bug). Force UTC when no offset/zone is present.
const ms = (s: string) => {
  const hasTz = /[zZ]|[+-]\d\d:?\d\d$/.test(s);
  return new Date(hasTz ? s : s + "Z").getTime();
};

export const ago = (iso?: string | null) => {
  if (!iso) return "—";
  const d = Math.max(0, (Date.now() - ms(iso)) / 1000);
  if (d < 60) return `${Math.floor(d)}s ago`;
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
};

export const dur = (a?: string | null, b?: string | null) => {
  if (!a) return "—";
  const end = b ? ms(b) : Date.now();
  const s = Math.max(0, (end - ms(a)) / 1000);
  return s < 60 ? `${s.toFixed(0)}s` : `${(s / 60).toFixed(1)}m`;
};

export const explorerUrl = (tx: string) =>
  tx.startsWith("0xmock")
    ? `#mock-tx-${tx.slice(0, 14)}`
    : `https://basescan.org/tx/${tx}`;
