"""Application configuration.

All secrets are read from the environment. Nothing sensitive is ever
hard-coded or logged. See `.env.example` for the full list.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "Hermesx402"
    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = True
    api_prefix: str = "/api"

    # --- Database ---
    # Local bring-up defaults to SQLite (aiosqlite). docker-compose overrides
    # with the async Postgres URL.
    database_url: str = "sqlite+aiosqlite:///./agentledger.db"

    # --- Auth (Privy wallet connect) ---
    # "privy": verify Privy access tokens (real wallet connect).
    # "dev":   no Privy app configured — accept an X-Dev-User header so the
    #          app still runs locally / in tests. Set PRIVY_APP_ID to flip.
    # Free trial credit granted to every new user; the platform (house
    # wallet) covers x402 spend up to this, then the user's own wallet pays.
    signup_credit_usd: str = "1.00"
    # Charged per run for the agent's real LLM + web-search usage (these
    # OpenRouter calls cost real money). Debited from trial credit, then the
    # user's wallet. Honest usage billing, not simulated.
    run_usage_fee_usd: str = "0.12"

    auth_mode: Literal["privy", "dev"] = "dev"
    privy_app_id: str | None = None
    privy_app_secret: str | None = None  # server-side Privy API (not for JWT)
    # Optional PEM public key; if unset we verify via Privy's JWKS using the
    # app id (no extra secret needed).
    privy_verification_key: str | None = None

    @property
    def privy_jwks_url(self) -> str | None:
        if not self.privy_app_id:
            return None
        return f"https://auth.privy.io/api/v1/apps/{self.privy_app_id}/jwks.json"

    # --- Payment layer (x402) ---
    # The single most important flag in the system. "mock" runs the explicitly
    # permitted local scaffolding (no real money). "x402" uses the real
    # Coinbase x402 SDK + facilitator. See README "Path to real".
    payment_provider: Literal["mock", "x402"] = "mock"
    x402_network: str = "eip155:8453"  # Base mainnet by default when real
    x402_facilitator_url: str = "https://x402.org/facilitator"
    # Server-side custody only. NEVER sent to the client. Empty in mock mode.
    x402_evm_private_key: str | None = None
    x402_svm_private_key: str | None = None  # base58 Solana key (SVM path)
    x402_asset_address: str | None = None  # USDC mint/contract for the network
    x402_pay_to: str | None = None  # resource-server receiving address
    # SVM only: the account that sponsors the Solana tx fee + co-signs the
    # settlement. Normally discovered from the facilitator's /supported; this
    # is an explicit override if you run your own facilitator.
    x402_fee_payer: str | None = None

    # --- Agent reasoning via OpenRouter (real LLM, OpenAI-compatible) ---
    openrouter_api_key: str | None = None
    openrouter_model: str = "nousresearch/hermes-3-llama-3.1-70b"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Mock paid API (build-stage scaffolding) ---
    mock_api_base_url: str = "http://localhost:8000/mockapi"
    mock_api_price_usdc: str = "0.01"

    # --- Worker ---
    redis_url: str = "redis://localhost:6379/0"
    run_mode: Literal["inproc", "arq"] = "inproc"  # inproc = no Redis needed

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    # --- Rate limits (requests / window seconds) ---
    rate_limit_auth: int = 10
    rate_limit_auth_window: int = 60
    rate_limit_run_create: int = 5
    rate_limit_run_window: int = 60

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
