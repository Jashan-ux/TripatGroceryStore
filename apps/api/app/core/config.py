"""Typed, validated application settings.

Every value comes from the environment (12-factor). Nothing here has a production
default: `Settings.validate_runtime()` refuses to boot a production process with
placeholder secrets, so a misconfigured deploy fails fast instead of leaking.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "production", "test"]

_PINCODE = re.compile(r"^\d{6}$")


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---------------------------------------------------------------
    APP_NAME: str = "Tripat Pansari · MSG Store API"
    ENVIRONMENT: Environment = "local"
    LOG_LEVEL: str = "INFO"
    #: Public origin of the frontend. Used for CORS allowlist and email links.
    WEB_ORIGIN: str = "http://localhost:5173"
    #: Extra allowed origins (staging previews), comma separated, never "*".
    CORS_EXTRA_ORIGINS: str = ""

    # --- Database -----------------------------------------------------------
    #: Pooled (transaction-mode) URL used by the app — statement cache disabled.
    DATABASE_URL: str = ""
    #: Direct (session-mode) URL used by Alembic only.
    DATABASE_DIRECT_URL: str = ""
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0, le=50)
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15_000, ge=500, le=120_000)

    # --- Supabase -----------------------------------------------------------
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_ISSUER: str = ""
    SUPABASE_STORAGE_BUCKET: str = "catalog"

    # --- Redis / rate limiting ---------------------------------------------
    REDIS_URL: str = ""
    RATE_LIMIT_ENABLED: bool = True
    #: slowapi limit strings, overridable per environment.
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_AUTHED: str = "240/minute"

    # --- Store / contact (seeded into store_settings, never hard-coded) -----
    STORE_PHONE: str = "+91 87089-73386"
    STORE_NAME: str = "Tripat Pansari MSG Store"
    STORE_ADDRESS: str = (
        "Tripat Pansari MSG Store, near Sabji Mandi, opposite Gyani Achhar Bhandaar, "
        "Mandi Dabwali, 125104"
    )
    STORE_MAPS_URL: str = ""
    FEEDBACK_EMAIL: str = "tripatinsan029@gmail.com"
    SUPPORT_EMAIL_FROM: str = "Tripat Pansari <orders@example.invalid>"

    # --- Email / push / bot protection -------------------------------------
    RESEND_API_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:tripatinsan029@gmail.com"
    TURNSTILE_SECRET_KEY: str = ""
    TURNSTILE_ENABLED: bool = False
    NOMINATIM_USER_AGENT: str = "TripatMSGStore/1.0 (tripatinsan029@gmail.com)"
    GOOGLE_OAUTH_CLIENT_IDS: str = ""

    # --- Feature flags ------------------------------------------------------
    PHONE_OTP_ENABLED: bool = False

    # --- Bootstrap ----------------------------------------------------------
    #: Comma separated; admin role is granted at seed time only. Never read at runtime
    #: to elevate a live request.
    ADMIN_EMAILS: str = ""

    # --- Optional services --------------------------------------------------
    SENTRY_DSN: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT in {"local", "test"}

    @property
    def admin_emails(self) -> list[str]:
        return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.WEB_ORIGIN]
        origins += [o.strip() for o in self.CORS_EXTRA_ORIGINS.split(",") if o.strip()]
        return [o.rstrip("/") for o in origins if o and o != "*"]

    @property
    def allowed_google_client_ids(self) -> list[str]:
        return [c.strip() for c in self.GOOGLE_OAUTH_CLIENT_IDS.split(",") if c.strip()]

    @property
    def jwt_issuer(self) -> str:
        if self.SUPABASE_JWT_ISSUER:
            return self.SUPABASE_JWT_ISSUER
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return f"{self.jwt_issuer.rstrip('/')}/.well-known/jwks.json"

    @model_validator(mode="after")
    def _validate_runtime(self) -> Settings:
        for origin in self.cors_origins:
            if origin != "*" and urlsplit(origin).scheme not in {"http", "https"}:
                raise ValueError(f"CORS origin must be absolute: {origin!r}")
        if self.is_production:
            problems: list[str] = []
            for field in (
                "DATABASE_URL",
                "SUPABASE_URL",
                "SUPABASE_ANON_KEY",
                "SUPABASE_SERVICE_ROLE_KEY",
                "STORE_MAPS_URL",
                "RESEND_API_KEY",
            ):
                if not getattr(self, field):
                    problems.append(f"{field} is required in production")
            if urlsplit(self.WEB_ORIGIN).scheme != "https":
                problems.append("WEB_ORIGIN must use https in production")
            if "*" in self.CORS_EXTRA_ORIGINS:
                problems.append("CORS_EXTRA_ORIGINS may not contain '*'")
            if not self.admin_emails:
                problems.append("ADMIN_EMAILS is required in production")
            if self.RATE_LIMIT_ENABLED and not self.REDIS_URL:
                problems.append(
                    "REDIS_URL is required in production: in-memory rate limits are per-instance"
                )
            if problems:
                raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    def public_config(self) -> dict[str, object]:
        """Non-secret config the frontend may load at runtime."""
        return {
            "environment": self.ENVIRONMENT,
            "store_phone": self.STORE_PHONE,
            "store_name": self.STORE_NAME,
            "store_address": self.STORE_ADDRESS,
            "store_maps_url": self.STORE_MAPS_URL,
            "feedback_email": self.FEEDBACK_EMAIL,
            "minimum_order_paise": 50_000,
            "serviceable_pincodes": ["125104", "125201"],
            "default_delivery_days": 1,
            "phone_otp_enabled": self.PHONE_OTP_ENABLED,
            "turnstile_enabled": self.TURNSTILE_ENABLED,
            "supabase_url": self.SUPABASE_URL,
            "supabase_anon_key": self.SUPABASE_ANON_KEY,
            "vapid_public_key": self.VAPID_PUBLIC_KEY,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def validate_pincode(value: str) -> bool:
    return bool(_PINCODE.match(value))
