"""Profiles, catalogue and store settings (Phase 1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import LoyaltyTier, UserRole


class Profile(Base, TimestampMixin):
    """One row per Supabase auth user. ``id`` is the auth user id.

    The role lives here — never in client-editable JWT metadata.
    """

    __tablename__ = "profiles"

    # The migration-owned FK to auth.users is cross-schema and intentionally
    # excluded from Alembic model comparison (see app.db.alembic_utils).
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # The PostgreSQL type is `user_role` (created by the migration); without the
    # explicit name SQLAlchemy would look for `userrole`.
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda enum: [m.value for m in enum]),
        nullable=False,
        server_default=text("'customer'::user_role"),
    )
    referral_code: Mapped[str] = mapped_column(String(12), nullable=False)
    referred_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    lifetime_spend_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    loyalty_tier: Mapped[LoyaltyTier] = mapped_column(
        SAEnum(
            LoyaltyTier, name="loyalty_tier", values_callable=lambda enum: [m.value for m in enum]
        ),
        nullable=False,
        server_default=text("'none'::loyalty_tier"),
    )
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("lifetime_spend_paise >= 0", name="lifetime_spend_non_negative"),
        Index("uq_profiles_email_lower", func.lower(text("email")), unique=True),
        Index(
            "uq_profiles_phone", "phone", unique=True, postgresql_where=text("phone IS NOT NULL")
        ),
        Index("uq_profiles_referral_code", "referral_code", unique=True),
    )


class Brand(Base, TimestampMixin):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("slug", name="uq_brands_slug"),
        Index("uq_brands_name_lower", func.lower(text("name")), unique=True),
    )


class Category(Base, TimestampMixin):
    """Top-level categories become storefront rails; children are subcategories."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    #: Either an emoji **or** an image — never emoji-only (defect 6.4).
    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    children: Mapped[list[Category]] = relationship(
        back_populates="parent", cascade="save-update", lazy="selectin"
    )
    parent: Mapped[Category | None] = relationship(
        back_populates="children", remote_side="Category.id"
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
        CheckConstraint("sort_order >= 0", name="sort_order_non_negative"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="no_self_parent"),
        Index("ix_categories_parent_sort", "parent_id", "sort_order"),
    )


class Product(Base, TimestampMixin):
    """A sellable item. Money is integer paise; ``stock`` is per product or variant."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    mrp_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    unit_label: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("10")
    )
    images: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    brand: Mapped[Brand | None] = relationship(lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_products_slug"),
        CheckConstraint("price_paise >= 0", name="price_non_negative"),
        CheckConstraint("mrp_paise >= 0", name="mrp_non_negative"),
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="low_stock_non_negative"),
        CheckConstraint("rating >= 0 AND rating <= 5", name="rating_range"),
        Index("ix_products_category_active", "category_id", "is_active"),
        Index("ix_products_brand", "brand_id"),
        Index("ix_products_price", "price_paise"),
        # Trigram index backs the ILIKE search used by the catalogue.
        Index(
            "ix_products_search_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index("ix_products_tags", "tags", postgresql_using="gin"),
    )


class ProductVariant(Base, TimestampMixin):
    """Weight/volume options — essential for loose herbs, spices and dals."""

    __tablename__ = "product_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    mrp_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    product: Mapped[Product] = relationship(back_populates="variants")

    __table_args__ = (
        UniqueConstraint("product_id", "label", name="uq_product_variants_product_label"),
        CheckConstraint("price_paise >= 0", name="variant_price_non_negative"),
        CheckConstraint("stock >= 0", name="variant_stock_non_negative"),
    )


class StoreSettings(Base, TimestampMixin):
    """Singleton row (id = 1). Every business number lives here, editable by admin."""

    __tablename__ = "store_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))

    # Storefront contact — never hard-coded in components.
    store_name: Mapped[str] = mapped_column(
        String(120), nullable=False, server_default="Tripat Pansari MSG Store"
    )
    store_phone: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="+91 87089-73386"
    )
    store_address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=(
            "Tripat Pansari MSG Store, near Sabji Mandi, opposite Gyani Achhar Bhandaar, "
            "Mandi Dabwali, 125104"
        ),
    )
    store_maps_url: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    feedback_email: Mapped[str] = mapped_column(
        String(320), nullable=False, server_default="tripatinsan029@gmail.com"
    )

    # Order rules
    minimum_order_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("50000")
    )
    serviceable_pincodes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{125104,125201}'::text[]")
    )
    default_delivery_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("10")
    )

    # Rewards
    referral_referrer_reward_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("2000")
    )
    referral_friend_discount_pct: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("10")
    )
    referral_credit_trigger: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="delivered"
    )
    scratch_threshold_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("200000")
    )
    scratch_min_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("5000")
    )
    scratch_max_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("10000")
    )
    scratch_expiry_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("30")
    )
    return_window_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("3")
    )
    tier_gold_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("2000000")
    )
    tier_platinum_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("5000000")
    )
    tier_diamond_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("10000000")
    )

    notification_email: Mapped[str] = mapped_column(String(320), nullable=False, server_default="")

    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("minimum_order_paise >= 0", name="minimum_order_non_negative"),
        CheckConstraint("scratch_min_paise <= scratch_max_paise", name="scratch_range_ordered"),
        CheckConstraint(
            "tier_gold_paise < tier_platinum_paise AND tier_platinum_paise < tier_diamond_paise",
            name="tiers_ordered",
        ),
        CheckConstraint("default_delivery_days >= 0", name="delivery_days_non_negative"),
    )
