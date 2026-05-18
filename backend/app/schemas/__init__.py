"""Pydantic v2 request/response schemas."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---
class AuthConfigOut(BaseModel):
    mode: str  # "privy" | "dev"
    privy_app_id: str | None


class UserOut(ORM):
    id: str
    privy_did: str
    email: str | None
    credit_remaining: Decimal
    payments_delegated: bool = False
    privy_wallet_address: str | None = None
    created_at: dt.datetime


class DelegateIn(BaseModel):
    wallet_id: str = Field(min_length=4, max_length=128)
    address: str = Field(min_length=32, max_length=64)


# --- Wallets ---
class WalletIn(BaseModel):
    address: str = Field(min_length=4, max_length=64)
    network: str = "eip155:8453"
    label: str = Field(default="Wallet", max_length=80)


class WalletRenameIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)


class WalletOut(ORM):
    id: str
    address: str
    network: str
    label: str
    is_primary: bool
    balance_cached: Decimal
    created_at: dt.datetime


# --- Agents ---
class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config_json: str = "{}"


class AgentOut(ORM):
    id: str
    wallet_id: str
    name: str
    config_json: str
    is_public: bool = False
    title: str | None = None
    description: str | None = None
    category: str | None = None
    price_per_run_usd: Decimal = Decimal("0")
    runs_rented: int = 0
    created_at: dt.datetime


class PublishIn(BaseModel):
    is_public: bool
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="General", max_length=48)
    price_per_run_usd: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class MarketplaceItem(ORM):
    id: str
    name: str
    title: str | None = None
    description: str | None = None
    category: str | None = None
    price_per_run_usd: Decimal = Decimal("0")
    runs_rented: int = 0
    created_at: dt.datetime


class EarningsOut(BaseModel):
    total_earned_usd: Decimal
    rented_runs: int
    by_agent: list[dict]


# --- Runs ---
class RunIn(BaseModel):
    agent_id: str
    goal: str = Field(min_length=3, max_length=2000)


class RunOut(ORM):
    id: str
    wallet_id: str
    agent_id: str
    goal: str
    status: str
    started_at: dt.datetime | None
    ended_at: dt.datetime | None
    total_spend: Decimal
    total_calls: int
    summary: str | None
    journal: str
    created_at: dt.datetime


# --- Payments / calls ---
class PaymentOut(ORM):
    id: str
    api_call_id: str
    run_id: str
    wallet_id: str
    amount: Decimal
    currency: str
    network: str
    tx_hash: str | None
    facilitator_ref: str | None
    status: str
    reconciled: bool
    reconcile_note: str | None
    created_at: dt.datetime


class ApiCallOut(ORM):
    id: str
    run_id: str
    wallet_id: str
    url: str
    method: str
    status_code: int | None
    paid: bool
    outcome: str
    purpose: str
    latency_ms: int | None
    created_at: dt.datetime


# --- Budget (per wallet) ---
class BudgetOut(ORM):
    daily_cap: Decimal
    per_tx_cap: Decimal
    per_run_cap: Decimal


class BudgetIn(BaseModel):
    daily_cap: Decimal = Field(gt=0)
    per_tx_cap: Decimal = Field(gt=0)
    per_run_cap: Decimal = Field(gt=0)


# --- Schedules (unattended recurring runs) ---
class ScheduleIn(BaseModel):
    agent_id: str
    goal: str = Field(min_length=3, max_length=2000)
    interval_seconds: int = Field(ge=60, le=2_592_000)  # 1 min … 30 days


class ScheduleOut(ORM):
    id: str
    agent_id: str
    goal: str
    interval_seconds: int
    active: bool
    next_run_at: dt.datetime
    last_run_at: dt.datetime | None
    runs_fired: int
    created_at: dt.datetime


# --- Dashboard aggregates ---
class SpendPoint(BaseModel):
    bucket: str
    amount: Decimal


class NamedAmount(BaseModel):
    name: str
    amount: Decimal
    count: int


class DashboardOut(BaseModel):
    total_spend: Decimal
    total_runs: int
    total_calls: int
    blocked_calls: int
    success_rate: float
    spend_over_time: list[SpendPoint]
    spend_by_api: list[NamedAmount]
    spend_by_agent: list[NamedAmount]
    top_apis_paid: list[NamedAmount]
    recent_runs: list[RunOut]
