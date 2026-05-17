export interface User {
  id: string;
  privy_did: string;
  email: string | null;
  created_at: string;
}
export interface Wallet {
  id: string;
  address: string;
  network: string;
  label: string;
  is_primary: boolean;
  balance_cached: string;
  created_at: string;
}
export interface Agent {
  id: string;
  wallet_id: string;
  name: string;
  config_json: string;
  created_at: string;
}
export interface Run {
  id: string; wallet_id: string; agent_id: string; goal: string;
  status: string; started_at: string | null; ended_at: string | null;
  total_spend: string; total_calls: number; summary: string | null;
  journal: string;
  created_at: string;
}
export interface Payment {
  id: string; api_call_id: string; run_id: string; wallet_id: string;
  amount: string; currency: string; network: string;
  tx_hash: string | null; facilitator_ref: string | null; status: string;
  reconciled: boolean; reconcile_note: string | null; created_at: string;
}
export interface ApiCall {
  id: string; run_id: string; wallet_id: string; url: string; method: string;
  status_code: number | null; paid: boolean; outcome: string;
  purpose: string; latency_ms: number | null; created_at: string;
}
export interface Schedule {
  id: string; agent_id: string; goal: string; interval_seconds: number;
  active: boolean; next_run_at: string; last_run_at: string | null;
  runs_fired: number; created_at: string;
}
export interface Budget { daily_cap: string; per_tx_cap: string; per_run_cap: string; }
export interface NamedAmount { name: string; amount: string; count: number; }
export interface Dashboard {
  total_spend: string; total_runs: number; total_calls: number;
  blocked_calls: number; success_rate: number;
  spend_over_time: { bucket: string; amount: string }[];
  spend_by_api: NamedAmount[]; spend_by_agent: NamedAmount[];
  top_apis_paid: NamedAmount[]; recent_runs: Run[];
}
export interface RunEvent { kind: string; ts?: number; data?: Record<string, any>; }
