"""marketplace + wallet/credit/journal columns added after 0001

Brings the Postgres schema up to the current models: trial credit, Privy
delegated-wallet fields, run journal + creator, and the agent-marketplace
columns. (SQLite auto-adds these in app startup; Postgres needs this.)

Revision ID: 0002_marketplace_and_wallets
Revises: 0001_initial
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_marketplace_and_wallets"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

NUM = sa.Numeric(38, 18)


def upgrade() -> None:
    # --- users: trial credit + Privy delegated wallet ---
    op.add_column(
        "users",
        sa.Column("credit_remaining", NUM, server_default="1",
                  nullable=False),
    )
    op.add_column("users", sa.Column("privy_wallet_id", sa.String(128)))
    op.add_column("users", sa.Column("privy_wallet_address", sa.String(64)))
    op.add_column(
        "users",
        sa.Column("payments_delegated", sa.Boolean(),
                  server_default=sa.false(), nullable=False),
    )

    # --- runs: persisted journal + marketplace creator ---
    op.add_column(
        "runs",
        sa.Column("journal", sa.Text(), server_default="[]",
                  nullable=False),
    )
    op.add_column("runs", sa.Column("creator_user_id", sa.String(36)))
    op.create_index("ix_runs_creator_user_id", "runs", ["creator_user_id"])

    # --- agents: marketplace listing ---
    op.add_column(
        "agents",
        sa.Column("is_public", sa.Boolean(), server_default=sa.false(),
                  nullable=False),
    )
    op.add_column("agents", sa.Column("title", sa.String(120)))
    op.add_column("agents", sa.Column("description", sa.Text()))
    op.add_column("agents", sa.Column("category", sa.String(48)))
    op.add_column(
        "agents",
        sa.Column("price_per_run_usd", NUM, server_default="0",
                  nullable=False),
    )
    op.add_column(
        "agents",
        sa.Column("runs_rented", sa.Integer(), server_default="0",
                  nullable=False),
    )
    op.create_index("ix_agents_is_public", "agents", ["is_public"])
    op.create_index("ix_agents_category", "agents", ["category"])


def downgrade() -> None:
    op.drop_index("ix_agents_category", "agents")
    op.drop_index("ix_agents_is_public", "agents")
    for c in ("runs_rented", "price_per_run_usd", "category",
              "description", "title", "is_public"):
        op.drop_column("agents", c)
    op.drop_index("ix_runs_creator_user_id", "runs")
    op.drop_column("runs", "creator_user_id")
    op.drop_column("runs", "journal")
    for c in ("payments_delegated", "privy_wallet_address",
              "privy_wallet_id", "credit_remaining"):
        op.drop_column("users", c)
