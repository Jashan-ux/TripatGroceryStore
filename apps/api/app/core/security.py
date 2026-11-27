"""Supabase JWT verification.

Every protected route goes through :func:`verify_token`. The rules:

* Signature verified against the project's JWKS (RS256/ES256/EdDSA). Keys are
  cached by ``kid`` with a bounded lifetime.
* ``iss`` must be our project's auth issuer, ``aud`` must be ``authenticated``,
  and ``exp`` / ``iat`` / ``sub`` are required.
* ``alg: none`` and algorithm confusion are impossible: the algorithm is taken
  from a fixed allow-list and must match the key type.
* A symmetric secret (``SUPABASE_JWT_SECRET``) is supported **only** outside
  production, for local development against a legacy project.

The role is *never* read from the token — it comes from ``profiles.role``
(see ``app/api/deps.py``). Metadata in the token is only used as a display-name
hint on first login.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.errors import UnauthenticatedError
from app.core.logging import get_logger

logger = get_logger(__name__)

ASYMMETRIC_ALGORITHMS = ["ES256", "RS256", "EdDSA"]
ALLOWED_ALGORITHMS = [*ASYMMETRIC_ALGORITHMS, "HS256"]
REQUIRED_CLAIMS = ["exp", "iat", "sub", "aud", "iss"]


@dataclass(frozen=True)
class TokenClaims:
    """The parts of the token we act on. Nothing here is trusted for authorisation."""

    sub: uuid.UUID
    email: str
    email_verified: bool
    provider: str | None
    audience: str
    issued_at: datetime
    expires_at: datetime
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def display_name(self) -> str:
        meta = self.raw.get("user_metadata") or {}
        for key in ("full_name", "name"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:120]
        return ""


class SigningKeyProvider(Protocol):
    """Anything that can resolve a signing key for a token (the real JWKS, or a test key)."""

    def get_signing_key(self, token: str) -> Any: ...  # pragma: no cover - protocol


class JwksProvider:
    """Thin wrapper around PyJWKClient with an explicit cache lifetime."""

    def __init__(self, url: str, *, cache_seconds: int = 300, timeout: int = 5) -> None:
        self.url = url
        self._client = PyJWKClient(
            url,
            cache_keys=True,
            lifespan=cache_seconds,
            timeout=timeout,
        )

    def get_signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token)


_provider: SigningKeyProvider | None = None


def get_signing_key_provider(settings: Settings | None = None) -> SigningKeyProvider:
    global _provider
    settings = settings or get_settings()
    if _provider is None:
        _provider = JwksProvider(settings.jwks_url)
    return _provider


def reset_signing_key_provider() -> None:
    """Test hook: drop the cached provider."""
    global _provider
    _provider = None


def _decode(
    token: str,
    *,
    settings: Settings,
    provider: SigningKeyProvider,
) -> dict[str, Any]:
    algorithms = list(ASYMMETRIC_ALGORITHMS)
    key: Any
    if settings.SUPABASE_JWT_SECRET and not settings.is_production:
        # Local/legacy projects may still sign with the shared secret.
        algorithms.append("HS256")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:  # pragma: no cover - malformed header
            raise UnauthenticatedError("Invalid token.") from exc
        if header.get("alg") == "HS256":
            key = settings.SUPABASE_JWT_SECRET
        else:
            key = provider.get_signing_key(token).key
    else:
        key = provider.get_signing_key(token).key

    try:
        return dict(
            jwt.decode(
                token,
                key=key,
                algorithms=algorithms,
                audience=settings.SUPABASE_JWT_AUDIENCE,
                issuer=settings.jwt_issuer,
                options={
                    "require": REQUIRED_CLAIMS,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_signature": True,
                },
            )
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthenticatedError("Your session has expired. Please sign in again.") from exc
    except jwt.InvalidAudienceError as exc:
        raise UnauthenticatedError("Invalid token audience.") from exc
    except jwt.InvalidIssuerError as exc:
        raise UnauthenticatedError("Invalid token issuer.") from exc
    except jwt.MissingRequiredClaimError as exc:
        raise UnauthenticatedError("Token is missing required claims.") from exc
    except jwt.PyJWTError as exc:
        logger.info("jwt_rejected", reason=type(exc).__name__)
        raise UnauthenticatedError("Invalid or expired session.") from exc


def claims_from_payload(payload: dict[str, Any]) -> TokenClaims:
    try:
        subject = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise UnauthenticatedError("Invalid token subject.") from exc

    email = payload.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise UnauthenticatedError("This account has no verified email address.")

    # Explicit `false` is rejected; an absent flag is allowed (older tokens).
    if payload.get("email_verified") is False:
        raise UnauthenticatedError("Please verify your email address first.")

    app_metadata = payload.get("app_metadata") or {}

    return TokenClaims(
        sub=subject,
        email=email.strip().lower(),
        email_verified=payload.get("email_verified") is not False,
        provider=app_metadata.get("provider") if isinstance(app_metadata, dict) else None,
        audience=str(payload.get("aud", "")),
        issued_at=datetime.fromtimestamp(int(payload["iat"]), tz=UTC),
        expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        raw=payload,
    )


def verify_token(
    token: str,
    *,
    settings: Settings | None = None,
    provider: SigningKeyProvider | None = None,
) -> TokenClaims:
    """Verify a bearer token and return its trusted claims."""
    if not token or token.count(".") != 2:
        raise UnauthenticatedError("Missing or malformed bearer token.")
    settings = settings or get_settings()
    provider = provider or get_signing_key_provider(settings)
    payload = _decode(token, settings=settings, provider=provider)
    return claims_from_payload(payload)
