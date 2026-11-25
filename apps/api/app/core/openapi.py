"""Shared OpenAPI response declarations.

Declaring the error responses once means:

* the published schema documents the single error shape on every endpoint, and
* ``openapi-typescript`` emits ``ErrorResponse`` / ``ErrorDetail`` into
  ``packages/api-client`` so the frontend parses errors with generated types
  instead of guessing.
"""

from __future__ import annotations

from typing import Any

from app.schemas.common import ErrorResponse

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing, expired or invalid token."},
    403: {"model": ErrorResponse, "description": "Authenticated but not allowed."},
    404: {"model": ErrorResponse, "description": "Resource not found or not owned by caller."},
    422: {"model": ErrorResponse, "description": "Validation failed."},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
}
