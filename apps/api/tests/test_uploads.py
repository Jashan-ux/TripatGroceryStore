"""Product photos: prove the shop re-encodes instead of trusting the file (S-08).

An image upload is the one place a stranger can hand the server a file. The
defence is simple and testable: decode it with a real image library, refuse
anything that is not JPEG/PNG/WebP, then throw the original bytes away and write
our own 1600px WebP. Nothing a file *claims* to be survives that.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

import pytest
from app.core.errors import ValidationError
from app.services import uploads
from httpx import AsyncClient
from PIL import Image

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("use_local_keys")]

ADMIN_EMAIL = "owner@example.com"


def _image_bytes(
    *,
    fmt: str = "PNG",
    size: tuple[int, int] = (800, 600),
    color: tuple[int, int, int] = (200, 90, 40),
    exif: bytes | None = None,
) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color)
    image.save(buffer, format=fmt, exif=exif) if exif else image.save(buffer, format=fmt)
    return buffer.getvalue()


def _error_code(exc_info: pytest.ExceptionInfo[ValidationError]) -> str:
    return str(exc_info.value.code)


# --------------------------------------------------------------------------- #
# Decoding
# --------------------------------------------------------------------------- #
def test_a_normal_photo_becomes_a_webp() -> None:
    result = uploads.normalise_image(_image_bytes())
    assert result.content_type == "image/webp"
    assert result.width == 800
    assert result.height == 600
    assert Image.open(io.BytesIO(result.data)).format == "WEBP"


def test_an_svg_is_refused_even_though_it_is_an_image() -> None:
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        b"<script>alert(1)</script></svg>"
    )
    with pytest.raises(ValidationError) as exc:
        uploads.normalise_image(svg)
    # An SVG never even decodes as a raster image, so it is refused as junk.
    assert _error_code(exc) == "image_unreadable"


def test_a_gif_is_refused() -> None:
    with pytest.raises(ValidationError) as exc:
        uploads.normalise_image(_image_bytes(fmt="GIF"))
    assert _error_code(exc) == "image_type_not_allowed"


def test_a_file_that_is_not_an_image_at_all_is_refused() -> None:
    with pytest.raises(ValidationError) as exc:
        uploads.normalise_image(b"<?php system($_GET['c']); ?>")
    assert _error_code(exc) == "image_unreadable"


def test_a_polyglot_jpeg_loses_its_payload() -> None:
    """A JPEG with PHP appended is a classic bypass. Re-encoding kills it."""
    payload = b'<?php system($_GET["cmd"]); ?>'
    raw = _image_bytes(fmt="JPEG") + payload
    result = uploads.normalise_image(raw)
    assert payload not in result.data
    assert b"<?php" not in result.data
    # And the result is a valid image, not just bytes with the payload stripped.
    assert Image.open(io.BytesIO(result.data)).size == (800, 600)


def test_exif_and_gps_are_stripped() -> None:
    exif = Image.Exif()
    exif[0x0110] = "Test Phone 12"  # Model
    raw = _image_bytes(fmt="JPEG", exif=exif.tobytes())
    assert b"Test Phone 12" in raw  # the original really carries it
    result = uploads.normalise_image(raw)
    assert b"Test Phone 12" not in result.data


def test_an_oversized_upload_is_refused_before_decoding() -> None:
    oversized = b"\xff\xd8\xff" + b"0" * uploads.MAX_UPLOAD_BYTES
    with pytest.raises(ValidationError) as exc:
        uploads.normalise_image(oversized)
    assert _error_code(exc) == "image_too_large"


def test_a_huge_camera_original_is_refused() -> None:
    with pytest.raises(ValidationError) as exc:
        uploads.normalise_image(_image_bytes(size=(4200, 200)))
    assert _error_code(exc) == "image_dimensions_too_large"


def test_a_tiny_placeholder_is_refused() -> None:
    with pytest.raises(ValidationError) as exc:
        uploads.normalise_image(_image_bytes(size=(20, 20)))
    assert _error_code(exc) == "image_too_small"


def test_a_very_wide_photo_is_scaled_down_to_the_storefront_size() -> None:
    result = uploads.normalise_image(_image_bytes(size=(3000, 1000)))
    assert max(result.width, result.height) == uploads.OUTPUT_MAX_EDGE
    assert result.width == 1600
    assert result.height == 533


# --------------------------------------------------------------------------- #
# Storing
# --------------------------------------------------------------------------- #
def test_object_keys_are_unique_and_dated() -> None:
    first = uploads._object_key("My Photo.JPG")
    second = uploads._object_key("My Photo.JPG")
    assert first != second
    assert first.endswith(".webp")
    assert first.startswith("products/")
    assert "my-photo" not in first, "the customer's filename must not survive verbatim"


async def test_storing_without_storage_configured_says_so_plainly() -> None:
    image = uploads.normalise_image(_image_bytes())
    with pytest.raises(Exception) as exc:  # UnavailableError
        await uploads.store_image(image, original_name="a.png")
    assert getattr(exc.value, "code", None) == "image_upload_unavailable"


# --------------------------------------------------------------------------- #
# Remote image links (used by the CSV importer)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "https://images.example.com/ghee.jpg",
        "https://cdn.shop.in/p/123.webp",
        "https://exampleshop.s3.ap-south-1.amazonaws.com/a.png",
    ],
)
def test_public_https_links_are_allowed(url: str) -> None:
    assert uploads.safe_remote_image_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://images.example.com/ghee.jpg",
        "https://169.254.169.254/latest/meta-data/",
        "https://127.0.0.1/a.png",
        "https://10.0.0.5/a.png",
        "https://localhost/a.png",
        "https://printer.local/a.png",
        "https://8.8.8.8/a.png",
        "javascript:alert(1)",
    ],
)
def test_links_that_could_reach_inside_the_network_are_refused(url: str) -> None:
    with pytest.raises(ValidationError):
        uploads.safe_remote_image_url(url)


def test_an_empty_link_is_simply_empty() -> None:
    assert uploads.safe_remote_image_url("") == ""


# --------------------------------------------------------------------------- #
# The endpoint
# --------------------------------------------------------------------------- #
@pytest.fixture()
async def admin(async_client: AsyncClient, make_token: Callable[..., str]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {make_token(ADMIN_EMAIL)}"}
    profile = (await async_client.get("/api/v1/me", headers=headers)).json()
    assert profile["role"] == "admin", profile
    return {"headers": headers}


async def _upload(async_client: AsyncClient, admin: dict[str, Any], data: bytes, name: str) -> Any:
    return await async_client.post(
        "/api/v1/admin/catalogue/images",
        files={"file": (name, data, "image/png")},
        headers=admin["headers"],
    )


async def test_the_endpoint_refuses_junk_with_a_readable_message(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await _upload(async_client, admin, b"not an image", "evil.svg")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "image_unreadable"


async def test_the_endpoint_refuses_an_oversized_file(
    async_client: AsyncClient, admin: dict[str, Any]
) -> None:
    response = await _upload(
        async_client, admin, b"\xff\xd8\xff" + b"0" * uploads.MAX_UPLOAD_BYTES, "big.jpg"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "image_too_large"


async def test_uploads_are_owner_only(async_client: AsyncClient, customer: dict[str, Any]) -> None:
    response = await async_client.post(
        "/api/v1/admin/catalogue/images",
        files={"file": ("a.png", _image_bytes(), "image/png")},
        headers=customer["headers"],
    )
    assert response.status_code == 403


async def test_a_valid_photo_is_stored_and_the_url_come_back(
    async_client: AsyncClient, admin: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Storage is mocked — the sandbox has no Supabase bucket — but every step
    the shop controls (validate, re-encode, key, public URL) really runs."""
    seen: dict[str, Any] = {}

    class _Response:
        status_code = 200
        text = "ok"

    class _Client:
        async def post(self, url: str, **kwargs: Any) -> _Response:
            seen["url"] = url
            seen["content_type"] = kwargs["headers"]["Content-Type"]
            seen["body"] = kwargs["content"]
            return _Response()

    monkeypatch.setattr(
        uploads,
        "_storage_ready",
        lambda: ("https://proj.supabase.co", "svc-key", "product-images"),
    )

    result = await uploads.upload_product_image(
        _image_bytes(size=(900, 700)),
        filename="coriander bunch.png",
        client=_Client(),  # type: ignore[arg-type]
    )
    assert result.content_type == "image/webp"
    assert result.width == 900 and result.height == 700
    assert result.url.startswith(
        "https://proj.supabase.co/storage/v1/object/public/product-images/products/"
    )
    # The key is random and dated; the customer's filename is not in it.
    assert "coriander" not in result.url
    assert "/20" in result.url  # YYYY/MM
    assert seen["url"].startswith("https://proj.supabase.co/storage/v1/object/product-images/")
    assert seen["content_type"] == "image/webp"
    assert seen["body"][:4] == b"RIFF", "what lands in storage is the re-encoded WebP"
