"""Product images: the only place the shop uploads a file, so the only place to be careful.

The rule that makes this safe is boring and effective: **never store the bytes the
browser sent.** Whatever arrives is decoded, checked, re-encoded from scratch as
WebP with no metadata, and only then uploaded. That single step kills the classes
of upload attack that matter here:

* an SVG carrying script (never decoded, so rejected outright),
* a "JPEG" whose real payload starts with ``<?php`` (the trailing bytes are not
  part of the decoded pixels and do not survive the re-encode),
* EXIF carrying GPS or a payload (metadata is dropped),
* a zip bomb of pixels (dimensions are checked before decoding a full frame),
* anything larger than the limit (checked before reading into Pillow).

Two other guards live here as well: an image URL from a spreadsheet may only be
``https`` on a public host (no ``http://169.254.169.254`` SSRF), and the storage
upload is the single call that knows about Supabase.
"""

from __future__ import annotations

import io
import ipaddress
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import ConflictError, UnavailableError, ValidationError
from app.core.logging import get_logger
from app.schemas.admin_catalogue import ImageOut

logger = get_logger(__name__)

#: 2 MB is generous for a grocery photo and small enough to stay polite on 4G.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
#: Anything bigger is a camera original, not a catalogue image.
MAX_SOURCE_EDGE = 4000
#: What the storefront actually renders. Down-scaling also drops any stowaway.
OUTPUT_MAX_EDGE = 1600
OUTPUT_QUALITY = 82
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
STORAGE_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class NormalisedImage:
    data: bytes
    width: int
    height: int
    content_type: str = "image/webp"


def normalise_image(raw: bytes) -> NormalisedImage:
    """Decode, sanity-check and re-encode. Raises ``ValidationError`` on junk."""
    if not raw:
        raise ValidationError("That file is empty.", code="image_empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Images must be under {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            code="image_too_large",
            details={"bytes": len(raw), "max_bytes": MAX_UPLOAD_BYTES},
        )

    try:
        # Opening reads only the header; `verify()` then checks the structure
        # without decoding pixels, which is what rejects a truncated file early.
        with Image.open(io.BytesIO(raw)) as probe:
            detected = (probe.format or "").upper()
            probe.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError(
            "That file is not an image we can read. Use a JPEG, PNG or WebP photo.",
            code="image_unreadable",
            details={"reason": str(exc)[:120]},
        ) from exc

    if detected not in ALLOWED_FORMATS:
        raise ValidationError(
            "Only JPEG, PNG and WebP photos are accepted.",
            code="image_type_not_allowed",
            details={"detected": detected or "unknown", "allowed": sorted(ALLOWED_FORMATS)},
        )

    # `verify()` leaves the file object unusable, so the real work reopens it.
    try:
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if width > MAX_SOURCE_EDGE or height > MAX_SOURCE_EDGE:
                raise ValidationError(
                    f"Photos must be at most {MAX_SOURCE_EDGE}px on each side.",
                    code="image_dimensions_too_large",
                    details={"width": width, "height": height},
                )
            if width < 40 or height < 40:
                raise ValidationError(
                    "That photo is too small to show in the shop (minimum 40×40).",
                    code="image_too_small",
                    details={"width": width, "height": height},
                )
            image = image.convert("RGBA" if image.mode in {"RGBA", "LA", "P"} else "RGB")
            image.thumbnail((OUTPUT_MAX_EDGE, OUTPUT_MAX_EDGE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            # No `exif`, no `icc_profile`: the re-encode keeps pixels only.
            image.save(out, format="WEBP", quality=OUTPUT_QUALITY, method=4)
            data = out.getvalue()
            final_width, final_height = image.size
    except ValidationError:
        raise
    except (OSError, ValueError) as exc:
        raise ValidationError(
            "That image could not be processed.",
            code="image_unreadable",
            details={"reason": str(exc)[:120]},
        ) from exc

    return NormalisedImage(data=data, width=final_width, height=final_height)


# --------------------------------------------------------------------------- #
# Remote image URLs (the bulk importer accepts a link per row)
# --------------------------------------------------------------------------- #
def safe_remote_image_url(url: str) -> str:
    """Only public https hosts. Rejects metadata endpoints and plain http."""
    candidate = (url or "").strip()
    if not candidate:
        return ""
    parts = urlsplit(candidate)
    if parts.scheme != "https":
        raise ValidationError(
            "Image links must start with https://.",
            code="image_url_not_https",
            details={"url": candidate[:200]},
        )
    host = (parts.hostname or "").strip()
    if not host:
        raise ValidationError(
            "That image link has no host.",
            code="image_url_invalid",
            details={"url": candidate[:200]},
        )
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValidationError(
            "Image links must point at a public site.",
            code="image_url_private_host",
            details={"url": candidate[:200]},
        )
    # A literal IP is refused outright: this is a catalogue, not an API client.
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return candidate
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise ValidationError(
            "Image links must point at a public site.",
            code="image_url_private_host",
            details={"url": candidate[:200]},
        )
    raise ValidationError(
        "Use a domain name for image links, not a bare IP address.",
        code="image_url_bare_ip",
        details={"url": candidate[:200]},
    )


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def _storage_ready() -> tuple[str, str, str]:
    settings = get_settings()
    base = settings.SUPABASE_URL.rstrip("/")
    if not base or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise UnavailableError(
            "Image storage is not configured on this server yet "
            "(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY).",
            code="storage_not_configured",
        )
    return base, settings.SUPABASE_SERVICE_ROLE_KEY, settings.SUPABASE_STORAGE_BUCKET


def _object_key(original_name: str) -> str:
    """Random, dated and extension-fixed: never the visitor's filename."""
    stamp = datetime.now(tz=UTC).strftime("%Y/%m")
    return f"products/{stamp}/{uuid.uuid4().hex}{secrets.token_hex(2)}.webp"


def public_url(base: str, bucket: str, key: str) -> str:
    return f"{base}/storage/v1/object/public/{bucket}/{key}"


async def store_image(
    image: NormalisedImage, *, original_name: str, client: httpx.AsyncClient | None = None
) -> str:
    """Upload the normalised WebP and return its public URL."""
    base, service_key, bucket = _storage_ready()
    key = _object_key(original_name)
    endpoint = f"{base}/storage/v1/object/{bucket}/{key}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": image.content_type,
        "cache-control": "public, max-age=31536000, immutable",
        "x-upsert": "false",
    }

    owned = client is None
    http = client or httpx.AsyncClient(timeout=STORAGE_TIMEOUT_SECONDS)
    try:
        response = await http.post(endpoint, content=image.data, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("storage_upload_failed", error=str(exc)[:200])
        raise UnavailableError(
            "The image could not be uploaded right now. Try again in a moment.",
            code="image_upload_unavailable",
        ) from exc
    finally:
        if owned:
            await http.aclose()

    if response.status_code not in {200, 201}:
        logger.warning(
            "storage_rejected_upload", status=response.status_code, body=response.text[:200]
        )
        raise ConflictError(
            "Storage refused that image.",
            code="image_upload_failed",
            details={"status": response.status_code},
        )
    return public_url(base, bucket, key)


async def upload_product_image(
    raw: bytes, *, filename: str, client: httpx.AsyncClient | None = None
) -> ImageOut:
    image = normalise_image(raw)
    url = await store_image(image, original_name=filename, client=client)
    return ImageOut(
        url=url,
        width=image.width,
        height=image.height,
        bytes=len(image.data),
        content_type=image.content_type,
    )


__all__ = [
    "ALLOWED_FORMATS",
    "MAX_UPLOAD_BYTES",
    "NormalisedImage",
    "normalise_image",
    "public_url",
    "safe_remote_image_url",
    "store_image",
    "upload_product_image",
]
