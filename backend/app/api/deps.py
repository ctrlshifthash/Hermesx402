"""Shared API deps: Privy identity → User, wallet scoping, rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.privy import AuthError, verify_privy_token
from app.db.session import get_db
from app.models import User, Wallet

# Anti-abuse: the $1 trial credit is per-IP, not per-guest-id. Clearing
# localStorage mints a new guest id, but the same machine only gets the
# free credit once per window — so it can't farm unlimited real LLM spend.
# In-memory (resets on restart) — deliberately simple; a restart re-opening
# the window is an acceptable trade vs. a new table. Signed-in (Privy) users
# are identity-bound and always get credit.
_GUEST_CREDIT_IPS: dict[str, float] = {}
_GUEST_CREDIT_WINDOW = 86_400  # 24h


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
    x_guest_id: str | None = Header(default=None),
) -> User:
    """Resolve the caller to a User, upserting on first sight.

    Priority:
    1. Privy bearer token (a signed-in user) — when present & valid.
    2. `X-Guest-Id` — a frictionless anonymous session; no sign-in required.
       Every guest still gets the $1 credit + default wallet.
    3. Dev mode `X-Dev-User` (no Privy app configured).
    Sign-in is therefore optional: a guest can use everything immediately
    and later sign in / connect a wallet to persist or fund beyond trial.
    """
    did: str
    email: str | None = None
    has_bearer = bool(
        authorization and authorization.lower().startswith("bearer ")
    )
    if settings.auth_mode == "privy" and has_bearer:
        try:
            ident = verify_privy_token(authorization.split(" ", 1)[1])
        except AuthError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))
        did, email = ident.did, ident.email
    elif x_guest_id:
        did = f"guest:{x_guest_id}"
    elif settings.auth_mode != "privy":
        did = f"dev:{x_dev_user}" if x_dev_user else "dev:local"
    else:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "No identity (guest or sign-in)"
        )

    user = (
        await db.execute(select(User).where(User.privy_did == did))
    ).scalar_one_or_none()
    if user is None:
        import time as _t  # noqa: PLC0415
        from decimal import Decimal  # noqa: PLC0415

        from sqlalchemy.exc import IntegrityError  # noqa: PLC0415

        # Full trial credit for signed-in users always; for guests only the
        # first time per IP within the window (anti-farm). Repeat guests from
        # the same machine get $0 — they can still browse, but must connect &
        # fund a wallet to actually run agents (real LLM cost is gated).
        grant = Decimal(settings.signup_credit_usd)
        if did.startswith("guest:"):
            ip = _client_ip(request)
            now = _t.time()
            last = _GUEST_CREDIT_IPS.get(ip)
            if last is not None and (now - last) < _GUEST_CREDIT_WINDOW:
                grant = Decimal("0")
            else:
                _GUEST_CREDIT_IPS[ip] = now

        user = User(
            privy_did=did,
            email=email,
            credit_remaining=grant,
        )
        db.add(user)
        try:
            await db.flush()
            # Every account starts ready: a default wallet container + budget
            # so the $1 free credit is usable immediately — no connect/link
            # step. A real wallet is only linked later to fund beyond trial.
            from app.models import Agent, Budget, Wallet  # noqa: PLC0415

            w = Wallet(
                user_id=user.id,
                address=f"trial:{did[-24:]}",
                network=settings.x402_network,
                label="Trial",
                is_primary=True,
                balance_cached=Decimal("0"),
            )
            db.add(w)
            await db.flush()
            db.add(Budget(wallet_id=w.id))
            # Default agent so the wallet is immediately usable for runs /
            # schedules (rename/add more in the Agents tab).
            db.add(Agent(user_id=user.id, wallet_id=w.id,
                         name="Default Agent",
                         config_json='{"runner": "hermes"}'))
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            # Concurrent first-login requests race to create the same user;
            # the loser just reuses the row the winner created.
            await db.rollback()
            user = (
                await db.execute(
                    select(User).where(User.privy_did == did)
                )
            ).scalar_one()
    return user


async def get_wallet(
    wallet_id: str | None = None,
    x_wallet_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Wallet:
    """Resolve the active wallet for this user. Self-healing: a requested
    `wallet_id`/`X-Wallet-Id` that doesn't belong to the user (e.g. a stale
    id cached in the browser from a previous DB) falls back to the user's
    primary wallet instead of erroring. Only errors if the user genuinely
    has zero wallets (every account is auto-provisioned one, so rare)."""
    wid = wallet_id or x_wallet_id
    own = list(
        (
            await db.execute(
                select(Wallet)
                .where(Wallet.user_id == user.id)
                .order_by(Wallet.is_primary.desc(), Wallet.created_at.asc())
            )
        ).scalars()
    )
    if not own:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No wallet — add one")
    if wid:
        match = next((w for w in own if w.id == wid), None)
        if match is not None:
            return match
        # stale / foreign id → fall back to primary rather than 404
    return own[0]


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, bucket: str, limit: int, window: int):
        async def dep(request: Request) -> None:
            ip = request.client.host if request.client else "unknown"
            key = f"{bucket}:{ip}"
            now = time.time()
            q = self._hits[key]
            while q and q[0] < now - window:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Rate limit exceeded for {bucket}",
                )
            q.append(now)

        return dep


rate_limiter = RateLimiter()
