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
    ReturnStatus,
    ScratchCardStatus,
    UserRole,
)
from app.models.notifications import EmailMessage, Notification
from app.models.orders import Address, Order, OrderEvent, OrderItem

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
    "OrderStatus",
    "PaymentMethod",
    "PaymentStatus",
    "Product",
    "ProductVariant",
    "Profile",
    "ReturnStatus",
    "ScratchCardStatus",
    "StoreSettings",
    "UserRole",
]
