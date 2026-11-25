"""Versioned API router — every group is mounted here.

Groups (implemented across phases): me, catalogue, cart, addresses,
orders/checkout, wallet & rewards, returns, notifications & push, feedback,
admin/*.  Admin routers are mounted under /admin and are the *only* place admin
code lives on the server; the frontend keeps admin code in a separate bundle.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import addresses, catalogue, checkout, me, orders, system
from app.api.v1.endpoints.admin import dashboard as admin_dashboard
from app.core.openapi import ERROR_RESPONSES

api_router = APIRouter(responses=ERROR_RESPONSES)
api_router.include_router(system.router)
api_router.include_router(me.router)
api_router.include_router(catalogue.router)
api_router.include_router(addresses.router)
api_router.include_router(checkout.router)
api_router.include_router(orders.router)
api_router.include_router(admin_dashboard.router)
