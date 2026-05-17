"""Privy access-token verification.

A Privy access token is an ES256 JWT: iss="privy.io", aud=<app id>,
sub=<privy user DID>. Verified offline against the app's public key. We fetch
that key from Privy's JWKS endpoint using only the (public) App ID — no extra
secret needed. A pasted PEM verification key is also supported as an override.

`auth_mode="dev"` skips Privy and trusts an `X-Dev-User` header so the app
still runs locally without a Privy app.
"""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.core.config import settings


@dataclass(frozen=True)
class PrivyIdentity:
    did: str
    email: str | None = None


class AuthError(Exception):
    pass


# Cache the JWKS client (it caches keys internally and refreshes on rotation).
_jwk_client: PyJWKClient | None = None


def _signing_key(token: str):
    global _jwk_client
    if settings.privy_verification_key:
        return settings.privy_verification_key
    if not settings.privy_jwks_url:
        raise AuthError("Privy not configured")
    if _jwk_client is None:
        _jwk_client = PyJWKClient(settings.privy_jwks_url)
    return _jwk_client.get_signing_key_from_jwt(token).key


def verify_privy_token(token: str) -> PrivyIdentity:
    if not settings.privy_app_id:
        raise AuthError("Privy not configured")
    try:
        key = _signing_key(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            audience=settings.privy_app_id,
            issuer="privy.io",
        )
    except AuthError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AuthError(f"invalid Privy token: {exc}") from exc
    sub = claims.get("sub")
    if not sub:
        raise AuthError("Privy token missing sub")
    return PrivyIdentity(did=sub, email=claims.get("email"))
