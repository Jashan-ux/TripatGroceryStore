"""Versioned API router — every group is mounted here.

Groups (implemented across phases): me, catalogue, cart, addresses,
orders/checkout, wallet & rewards, returns, notifications & push, feedback,
admin/*.  Admin routers are mounted under /admin and are the *only* place admin
code lives on the server; the frontend keeps admin code in a separate bundle.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    addresses,
    catalogue,
    checkout,
    feedback,
    me,
    notifications,
    offers,
    orders,
    returns,
    rewards,
    system,
)
from app.api.v1.endpoints.admin import analytics as admin_analytics
from app.api.v1.endpoints.admin import audit as admin_audit
from app.api.v1.endpoints.admin import catalogue as admin_catalogue
from app.api.v1.endpoints.admin import dashboard as admin_dashboard
from app.api.v1.endpoints.admin import feedback as admin_feedback
from app.api.v1.endpoints.admin import offers as admin_offers
from app.api.v1.endpoints.admin import orders as admin_orders
from app.api.v1.endpoints.admin import returns as admin_returns
from app.api.v1.endpoints.admin import settings as admin_settings
from app.core.openapi import ERROR_RESPONSES

api_router = APIRouter(responses=ERROR_RESPONSES)
api_router.include_router(system.router)
api_router.include_router(me.router)
api_router.include_router(catalogue.router)
api_router.include_router(addresses.router)
api_router.include_router(checkout.router)
api_router.include_router(orders.router)
api_router.include_router(notifications.router)
api_router.include_router(rewards.router)
api_router.include_router(returns.router)
api_router.include_router(offers.router)
api_router.include_router(feedback.router)
api_router.include_router(admin_dashboard.router)
api_router.include_router(admin_orders.router)
api_router.include_router(admin_returns.router)
api_router.include_router(admin_catalogue.router)
api_router.include_router(admin_offers.router)
api_router.include_router(admin_settings.router)
api_router.include_router(admin_feedback.router)
api_router.include_router(admin_analytics.router)
api_router.include_router(admin_audit.router)
