"""Storage configuration failures are actionable and safe to log."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from app.core.errors import UnavailableError
from app.services import uploads


@pytest.fixture()
def image() -> uploads.NormalisedImage:
    return uploads.NormalisedImage(data=b"webp bytes", width=80, height=80)


def test_a_blank_bucket_setting_is_rejected_before_a_storage_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BlankBucket:
        SUPABASE_URL = "https://project.supabase.co"
        SUPABASE_SERVICE_ROLE_KEY = "test-only-placeholder"
        SUPABASE_STORAGE_BUCKET = "  "

    monkeypatch.setattr(uploads, "get_settings", lambda: BlankBucket)
    with pytest.raises(UnavailableError) as exc:
        uploads._storage_ready()
    assert exc.value.code == "storage_bucket_not_configured"
    assert "SUPABASE_STORAGE_BUCKET" in exc.value.message
    assert exc.value.details == {}


async def test_a_missing_bucket_is_actionable_and_upstream_body_is_not_logged(
    monkeypatch: pytest.MonkeyPatch, image: uploads.NormalisedImage
) -> None:
    """A missing Storage bucket points operators to the exact safe config fix."""
    monkeypatch.setattr(
        uploads,
        "_storage_ready",
        lambda: ("https://project.supabase.co", "unit-test-only", "catalog"),
    )
    events: list[tuple[str, dict[str, Any]]] = []

    class RecordingLogger:
        def error(self, event: str, **fields: Any) -> None:
            events.append((event, fields))

        def warning(self, event: str, **fields: Any) -> None:
            events.append((event, fields))

    class MissingBucket:
        async def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
            return httpx.Response(
                404,
                json={"error": "NoSuchBucket", "message": "Bucket not found"},
                headers={"x-debug": "upstream details must not be logged"},
            )

    monkeypatch.setattr(uploads, "logger", RecordingLogger())
    with pytest.raises(UnavailableError) as exc:
        await uploads.store_image(image, original_name="photo.png", client=MissingBucket())  # type: ignore[arg-type]

    assert exc.value.status_code == 503
    assert exc.value.code == "storage_bucket_not_found"
    assert exc.value.details == {"bucket": "catalog"}
    assert "public-read" in exc.value.message
    assert "SUPABASE_URL" in exc.value.message
    assert "SUPABASE_STORAGE_BUCKET" in exc.value.message
    assert events == [("storage_bucket_missing", {"status": 404, "bucket": "catalog"})]
    assert "upstream details" not in repr(events)
