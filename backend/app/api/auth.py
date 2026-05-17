"""Auth: Privy wallet-connect identity. No passwords.

The frontend connects a wallet via Privy, obtains an access token, and sends
it as `Authorization: Bearer …`. The User row is upserted in the dependency.
`/auth/config` lets the frontend learn whether to run Privy or dev mode.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.schemas import AuthConfigOut, DelegateIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigOut)
async def auth_config():
    return AuthConfigOut(
        mode=settings.auth_mode,
        privy_app_id=settings.privy_app_id,
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/delegate", response_model=UserOut)
async def delegate_payments(
    body: DelegateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User granted the app delegated signing on their Privy wallet — record
    it so the agent can pay from their wallet once trial credit runs out."""
    user.privy_wallet_id = body.wallet_id
    user.privy_wallet_address = body.address
    user.payments_delegated = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/undelegate", response_model=UserOut)
async def revoke_delegation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.payments_delegated = False
    await db.commit()
    await db.refresh(user)
    return user
