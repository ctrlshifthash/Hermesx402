"""marketplace + wallet/credit/journal columns added after 0001 (idempotent)

0001_initial already defines some newer columns (credit_remaining, journal);
this only adds the ones genuinely missing (Privy delegated wallet, run
creator, agent-marketplace fields). Idempotent: safe to re-run, and safe
whether or not 0001 already has a given column.

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


def _cols(insp, table):
    return {c["name"] for c in insp.get_columns(table)}


def _idx(insp, table):
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    add = {
        "users": [
            ("privy_wallet_id", sa.Column("privy_wallet_id", sa.String(128))),
            ("privy_wallet_address",
             sa.Column("privy_wallet_address", sa.String(64))),
            ("payments_delegated",
             sa.Column("payments_delegated", sa.Boolean(),
                       server_default=sa.false(), nullable=False)),
            ("credit_remaining",
             sa.Column("credit_remaining", NUM, server_default="1",
                       nullable=False)),
        ],
        "runs": [
            ("journal", sa.Column("journal", sa.Text(),
                                  server_default="[]", nullable=False)),
            ("creator_user_id",
             sa.Column("creator_user_id", sa.String(36))),
        ],
        "agents": [
            ("is_public", sa.Column("is_public", sa.Boolean(),
                                    server_default=sa.false(),
                                    nullable=False)),
            ("title", sa.Column("title", sa.String(120))),
            ("description", sa.Column("description", sa.Text())),
            ("category", sa.Column("category", sa.String(48))),
            ("price_per_run_usd",
             sa.Column("price_per_run_usd", NUM, server_default="0",
                       nullable=False)),
            ("runs_rented", sa.Column("runs_rented", sa.Integer(),
                                      server_default="0", nullable=False)),
        ],
    }
    for table, cols in add.items():
        have = _cols(insp, table)
        for name, col in cols:
            if name not in have:
                op.add_column(table, col)

    idx = {
        "ix_runs_creator_user_id": ("runs", ["creator_user_id"]),
        "ix_agents_is_public": ("agents", ["is_public"]),
        "ix_agents_category": ("agents", ["category"]),
    }
    for name, (table, cols) in idx.items():
        if name not in _idx(insp, table):
            op.create_index(name, table, cols)


def downgrade() -> None:
    # Non-destructive: these columns are also created by 0001 in fresh DBs,
    # so downgrade is a no-op to avoid dropping shared columns.
    pass
