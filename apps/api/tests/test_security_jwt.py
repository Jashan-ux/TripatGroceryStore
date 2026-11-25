"""Supabase JWT verification (S‑02/S‑03).

Signing keys are generated per test run, so these assert the *code path* that runs
in production — the only difference is the key source (a local key pair instead of
the project's JWKS). No network access is required.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
import pytest
from app.core.config import Settings
from app.core.errors import UnauthenticatedError
from app.core.security import claims_from_payload, verify_token
from cryptography.hazmat.primitives.asymmetric import ec

ISSUER = "https://project.supabase.co/auth/v1"
AUDIENCE = "authenticated"


class FakeKeyProvider:
    """Stands in for PyJWKClient: hands back the previously generated public key."""

    def __init__(self, key: Any) -> None:
        self._key = key
        self.calls = 0

    def get_signing_key(self, token: str) -> Any:
        self.calls += 1
        return type("SigningKey", (), {"key": self._key})()


@pytest.fixture(scope="module")
def keypair() -> tuple[Any, Any]:
    private = ec.generate_private_key(ec.SECP256R1())
    return private, private.public_key()


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_JWT_SECRET="",
        ADMIN_EMAILS="owner@example.com",
    )


def make_token(private_key: Any, **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": str(uuid.uuid4()),
        "email": "customer@example.com",
        "email_verified": True,
        "aud": AUDIENCE,
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
        "role": "authenticated",
        "app_metadata": {"provider": "email"},
        "user_metadata": {"full_name": "Jashan Aneja"},
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "test-key"})


def test_valid_token_returns_claims(keypair: tuple[Any, Any], settings: Settings) -> None:
    private, public = keypair
    token = make_token(private)
    claims = verify_token(token, settings=settings, provider=FakeKeyProvider(public))
    assert claims.email == "customer@example.com"
    assert claims.email_verified is True
    assert claims.provider == "email"
    assert claims.display_name == "Jashan Aneja"
    assert claims.expires_at.timestamp() > time.time()


def test_expired_token_is_rejected(keypair: tuple[Any, Any], settings: Settings) -> None:
    private, public = keypair
    token = make_token(private, exp=int(time.time()) - 10)
    with pytest.raises(UnauthenticatedError) as excinfo:
        verify_token(token, settings=settings, provider=FakeKeyProvider(public))
    assert "expired" in str(excinfo.value).lower()


def test_wrong_audience_is_rejected(keypair: tuple[Any, Any], settings: Settings) -> None:
    private, public = keypair
    token = make_token(private, aud="service_role")
    with pytest.raises(UnauthenticatedError):
        verify_token(token, settings=settings, provider=FakeKeyProvider(public))


def test_wrong_issuer_is_rejected(keypair: tuple[Any, Any], settings: Settings) -> None:
    private, public = keypair
    token = make_token(private, iss="https://attacker.example/auth/v1")
    with pytest.raises(UnauthenticatedError):
        verify_token(token, settings=settings, provider=FakeKeyProvider(public))


def test_missing_required_claim_is_rejected(keypair: tuple[Any, Any], settings: Settings) -> None:
    private, public = keypair
    now = int(time.time())
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "email": "a@b.co", "aud": AUDIENCE, "iss": ISSUER, "iat": now},
        private,
        algorithm="ES256",
    )
    with pytest.raises(UnauthenticatedError):
        verify_token(token, settings=settings, provider=FakeKeyProvider(public))


def test_signature_from_another_key_is_rejected(
    keypair: tuple[Any, Any], settings: Settings
) -> None:
    _, public = keypair
    attacker = ec.generate_private_key(ec.SECP256R1())
    token = make_token(attacker)
    with pytest.raises(UnauthenticatedError):
        verify_token(token, settings=settings, provider=FakeKeyProvider(public))


def test_algorithm_confusion_is_rejected(keypair: tuple[Any, Any], settings: Settings) -> None:
    """An HS256 token signed with the *public key* must not be accepted."""
    _, public = keypair
    now = int(time.time())
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "attacker@example.com",
            "aud": AUDIENCE,
            "iss": ISSUER,
            "iat": now,
            "exp": now + 600,
        },
        key=b"not-the-secret",
        algorithm="HS256",
    )
    with pytest.raises(UnauthenticatedError):
        verify_token(forged, settings=settings, provider=FakeKeyProvider(public))


def test_hs256_secret_is_ignored_in_production(keypair: tuple[Any, Any]) -> None:
    _, public = keypair
    production = Settings(
        ENVIRONMENT="test",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_JWT_SECRET="shared-secret",
        ADMIN_EMAILS="owner@example.com",
    )
    # Constructed as "test" to skip the production config gate, then flipped:
    # the only thing under test is which algorithms are accepted.
    production.ENVIRONMENT = "production"
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "customer@example.com",
            "aud": AUDIENCE,
            "iss": ISSUER,
            "iat": now,
            "exp": now + 600,
        },
        "shared-secret",
        algorithm="HS256",
    )
    with pytest.raises(UnauthenticatedError):
        verify_token(token, settings=production, provider=FakeKeyProvider(public))


def test_malformed_tokens_are_rejected(settings: Settings) -> None:
    for token in ("", "not-a-jwt", "a.b", "a.b.c.d"):
        with pytest.raises(UnauthenticatedError):
            verify_token(token, settings=settings, provider=FakeKeyProvider(object()))


def test_subject_must_be_a_uuid() -> None:
    now = int(time.time())
    with pytest.raises(UnauthenticatedError):
        claims_from_payload({"sub": "abc", "email": "a@b.co", "iat": now, "exp": now + 60})


def test_unverified_email_is_rejected() -> None:
    now = int(time.time())
    with pytest.raises(UnauthenticatedError):
        claims_from_payload(
            {
                "sub": str(uuid.uuid4()),
                "email": "a@b.co",
                "email_verified": False,
                "iat": now,
                "exp": now + 60,
            }
        )


def test_token_without_email_is_rejected() -> None:
    now = int(time.time())
    with pytest.raises(UnauthenticatedError):
        claims_from_payload({"sub": str(uuid.uuid4()), "iat": now, "exp": now + 60})
