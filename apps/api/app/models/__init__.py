"""ORM models.

Importing this package registers every table on ``Base.metadata``. Alembic and
the drift check depend on that, so new model modules must be listed here.
"""

from app.models.base import Base
from app.models.catalogue import (
    Brand,
    Category,
    Product,
    ProductVariant,
    Profile,
    StoreSettings,
)
from app.models.enums import (
    EmailStatus,
    LoyaltyTier,
    NotificationKind,
    OfferAudience,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ReferralStatus,
    ReturnStatus,
    ScratchCardStatus,
    UserRole,
    WalletReason,
)
from app.models.notifications import EmailMessage, Notification
from app.models.orders import Address, Order, OrderEvent, OrderItem
from app.models.returns import OrderReturn, ReturnItem
from app.models.rewards import Referral, ScratchCard, Wallet, WalletEntry

__all__ = [
    "Address",
    "Base",
    "Brand",
    "Category",
    "EmailMessage",
    "EmailStatus",
    "LoyaltyTier",
    "Notification",
    "NotificationKind",
    "OfferAudience",
    "Order",
    "OrderEvent",
    "OrderItem",
    "OrderReturn",
    "OrderStatus",
    "PaymentMethod",
    "PaymentStatus",
    "Product",
    "ProductVariant",
    "Profile",
    "Referral",
    "ReferralStatus",
    "ReturnItem",
    "ReturnStatus",
    "ScratchCard",
    "ScratchCardStatus",
    "StoreSettings",
    "UserRole",
    "Wallet",
    "WalletEntry",
    "WalletReason",
]
