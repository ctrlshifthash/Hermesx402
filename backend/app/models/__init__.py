"""SQLAlchemy ORM models.

Identity is a Privy user (no passwords). One user owns MANY wallets; each
wallet has its own budget caps and its own agent(s); each agent has runs;
payments/calls are scoped to a wallet. Money is NUMERIC(38,18). All FKs and
created_at columns are indexed.
"""
from __future__ import annotations

import datetime as dt
import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    stopped = "stopped"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    settled = "settled"
    failed = "failed"
    blocked_budget = "blocked_budget"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Privy user DID, e.g. "did:privy:abc123". The sole identity key.
    privy_did: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    # Free trial credit: platform covers x402 spend up to this; then the
    # user's own connected wallet pays. Granted on signup.
    credit_remaining: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), default=Decimal("1")
    )
    # Once trial credit is exhausted, the agent pays from the USER'S OWN
    # Privy wallet — only if they delegated signing to the app (one tap).
    # We store their Privy wallet id/address + the delegation flag; the
    # server never holds their key (Privy signs on request).
    privy_wallet_id: Mapped[str | None] = mapped_column(String(128))
    privy_wallet_address: Mapped[str | None] = mapped_column(String(64))
    payments_delegated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    wallets: Mapped[list["Wallet"]] = relationship(back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("user_id", "address", name="uq_user_wallet"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    address: Mapped[str] = mapped_column(String(64), index=True)
    network: Mapped[str] = mapped_column(String(32), default="eip155:8453")
    label: Mapped[str] = mapped_column(String(80), default="Wallet")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    # Cached display balance. Reconciliation/refresh updates from chain.
    balance_cached: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), default=Decimal("0")
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    user: Mapped[User] = relationship(back_populates="wallets")
    budget: Mapped["Budget"] = relationship(back_populates="wallet", uselist=False)


class Budget(Base):
    """Caps are per WALLET — each wallet is an independent spending account."""

    __tablename__ = "budgets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    wallet_id: Mapped[str] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), unique=True, index=True
    )
    daily_cap: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=Decimal("5"))
    per_tx_cap: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), default=Decimal("0.50")
    )
    per_run_cap: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), default=Decimal("2")
    )
    wallet: Mapped[Wallet] = relationship(back_populates="budget")


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wallet_id: Mapped[str] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    # --- Marketplace: an agent can be published for others to rent ---
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(48), index=True)
    # What a renter pays the creator per run (USD). 0 = free to run.
    price_per_run_usd: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), default=Decimal("0")
    )
    runs_rented: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wallet_id: Mapped[str] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    # Set when the run uses someone else's PUBLIC agent — this user earns
    # the creator fee. Null for your own agents.
    creator_user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.queued, index=True
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    total_spend: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=Decimal("0"))
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    # Persisted timeline (JSON list of {kind,text}) so the full conversation
    # always shows — survives restarts / opening the run late.
    journal: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class ApiCall(Base):
    __tablename__ = "api_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(10), default="GET")
    status_code: Mapped[int | None] = mapped_column(Integer)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(32), default="unpaid", index=True)
    purpose: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    api_call_id: Mapped[str] = mapped_column(
        ForeignKey("api_calls.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    currency: Mapped[str] = mapped_column(String(16), default="USDC")
    network: Mapped[str] = mapped_column(String(32))
    tx_hash: Mapped[str | None] = mapped_column(String(80), index=True)
    facilitator_ref: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.pending, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    reconcile_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class Memory(Base):
    """Persistent agent memory: facts/findings the agent chose to keep, plus
    auto-saved run conclusions. Recalled into future runs of the same agent."""

    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    kind: Mapped[str] = mapped_column(String(24), default="note")  # note|result
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class Schedule(Base):
    """Unattended recurring runs. The scheduler fires a Run for the agent
    every `interval_seconds`; each run is still budget/credit-enforced, so
    autonomous recurring spend is hard-capped."""

    __tablename__ = "schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wallet_id: Mapped[str] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    goal: Mapped[str] = mapped_column(Text)
    interval_seconds: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    next_run_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    last_run_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    runs_fired: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


Index("ix_payments_wallet_status", Payment.wallet_id, Payment.status)
Index("ix_api_calls_run_outcome", ApiCall.run_id, ApiCall.outcome)
Index("ix_runs_wallet", Run.wallet_id, Run.created_at)
Index("ix_memories_agent", Memory.agent_id, Memory.created_at)
Index("ix_schedules_due", Schedule.active, Schedule.next_run_at)
