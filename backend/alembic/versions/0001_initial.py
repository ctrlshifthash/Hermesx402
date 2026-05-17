"""initial schema (Privy identity, multi-wallet)

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

NUM = sa.Numeric(38, 18)
TS = sa.DateTime(timezone=True)
run_status = sa.Enum(
    "queued", "running", "done", "failed", "stopped", name="runstatus"
)
pay_status = sa.Enum(
    "pending", "settled", "failed", "blocked_budget", name="paymentstatus"
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("privy_did", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("credit_remaining", NUM, nullable=False,
                  server_default="1"),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_users_privy_did", "users", ["privy_did"], unique=True)
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "wallets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address", sa.String(64), nullable=False),
        sa.Column("network", sa.String(32), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("balance_cached", NUM, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("user_id", "address", name="uq_user_wallet"),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"])
    op.create_index("ix_wallets_address", "wallets", ["address"])
    op.create_index("ix_wallets_created_at", "wallets", ["created_at"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wallet_id", sa.String(36),
                  sa.ForeignKey("wallets.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("daily_cap", NUM, nullable=False),
        sa.Column("per_tx_cap", NUM, nullable=False),
        sa.Column("per_run_cap", NUM, nullable=False),
    )
    op.create_index("ix_budgets_wallet_id", "budgets", ["wallet_id"], unique=True)

    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wallet_id", sa.String(36),
                  sa.ForeignKey("wallets.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])
    op.create_index("ix_agents_wallet_id", "agents", ["wallet_id"])
    op.create_index("ix_agents_created_at", "agents", ["created_at"])

    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wallet_id", sa.String(36),
                  sa.ForeignKey("wallets.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("agent_id", sa.String(36),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("ended_at", TS),
        sa.Column("total_spend", NUM, nullable=False),
        sa.Column("total_calls", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("journal", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_runs_user_id", "runs", ["user_id"])
    op.create_index("ix_runs_wallet_id", "runs", ["wallet_id"])
    op.create_index("ix_runs_agent_id", "runs", ["agent_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])
    op.create_index("ix_runs_wallet", "runs", ["wallet_id", "created_at"])

    op.create_table(
        "api_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36),
                  sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wallet_id", sa.String(36),
                  sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("agent_id", sa.String(36),
                  sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_api_calls_run_id", "api_calls", ["run_id"])
    op.create_index("ix_api_calls_wallet_id", "api_calls", ["wallet_id"])
    op.create_index("ix_api_calls_agent_id", "api_calls", ["agent_id"])
    op.create_index("ix_api_calls_user_id", "api_calls", ["user_id"])
    op.create_index("ix_api_calls_outcome", "api_calls", ["outcome"])
    op.create_index("ix_api_calls_created_at", "api_calls", ["created_at"])
    op.create_index("ix_api_calls_run_outcome", "api_calls",
                    ["run_id", "outcome"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("api_call_id", sa.String(36),
                  sa.ForeignKey("api_calls.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("run_id", sa.String(36),
                  sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("wallet_id", sa.String(36),
                  sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", NUM, nullable=False),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("network", sa.String(32), nullable=False),
        sa.Column("tx_hash", sa.String(80)),
        sa.Column("facilitator_ref", sa.String(120)),
        sa.Column("status", pay_status, nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("reconciled", sa.Boolean(), nullable=False),
        sa.Column("reconcile_note", sa.Text()),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_payments_api_call_id", "payments", ["api_call_id"])
    op.create_index("ix_payments_run_id", "payments", ["run_id"])
    op.create_index("ix_payments_wallet_id", "payments", ["wallet_id"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_tx_hash", "payments", ["tx_hash"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_idempotency_key", "payments",
                    ["idempotency_key"], unique=True)
    op.create_index("ix_payments_created_at", "payments", ["created_at"])
    op.create_index("ix_payments_wallet_status", "payments",
                    ["wallet_id", "status"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("agent_id", sa.String(36),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id")),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_agent_id", "memories", ["agent_id"])
    op.create_index("ix_memories_created_at", "memories", ["created_at"])
    op.create_index("ix_memories_agent", "memories",
                    ["agent_id", "created_at"])

    op.create_table(
        "schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("wallet_id", sa.String(36),
                  sa.ForeignKey("wallets.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("agent_id", sa.String(36),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", TS, nullable=False),
        sa.Column("last_run_at", TS),
        sa.Column("runs_fired", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_schedules_user_id", "schedules", ["user_id"])
    op.create_index("ix_schedules_wallet_id", "schedules", ["wallet_id"])
    op.create_index("ix_schedules_agent_id", "schedules", ["agent_id"])
    op.create_index("ix_schedules_active", "schedules", ["active"])
    op.create_index("ix_schedules_next_run_at", "schedules", ["next_run_at"])
    op.create_index("ix_schedules_due", "schedules",
                    ["active", "next_run_at"])


def downgrade() -> None:
    for t in (
        "schedules", "memories", "audit_log", "payments", "api_calls",
        "runs", "agents", "budgets", "wallets", "users",
    ):
        op.drop_table(t)
    pay_status.drop(op.get_bind(), checkfirst=True)
    run_status.drop(op.get_bind(), checkfirst=True)
