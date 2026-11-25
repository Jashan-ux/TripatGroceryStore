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
    LoyaltyTier,
    OfferAudience,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ReturnStatus,
    ScratchCardStatus,
    UserRole,
)

__all__ = [
    "Base",
    "Brand",
    "Category",
    "LoyaltyTier",
    "OfferAudience",
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
