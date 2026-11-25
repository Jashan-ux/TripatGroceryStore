"""Versioned API router — every group is mounted here.

Groups (implemented across phases): me, catalogue, cart, addresses,
orders/checkout, wallet & rewards, returns, notifications & push, feedback,
admin/*.  Admin routers are mounted under /admin and are the *only* place admin
code lives on the server; the frontend keeps admin code in a separate bundle.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import system
from app.core.openapi import ERROR_RESPONSES

api_router = APIRouter(responses=ERROR_RESPONSES)
api_router.include_router(system.router)
