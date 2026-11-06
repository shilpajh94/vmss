"""Absolute URLs for the images emails show — the Visimio header logo and
the signed check-in QR (serve-email-images-by-url-and-complete-contact
design.md Decisions 2–3). Referencing images by URL instead of `cid:`
parts is what keeps a delivered email free of any attachment strip.

The QR URL's signature is its authorization, the same model as
`core/storage.py`'s local signed URLs, but with a lifetime tied to the
visit rather than a 300 s TTL — an email has to keep working in an inbox.
"""

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

from vmss_api.core.config import settings

EMAIL_ASSETS_PATH = "/api/v1/public/email-assets"
LOGO_FILENAME = "visimio-logo.png"
# The logo URL used while the product was named Guestify, still served so
# emails already in inboxes never show a broken image.
RETIRED_LOGO_FILENAMES = ("guestify-logo.png",)
# How long after the visit window closes the pass stays viewable.
QR_URL_GRACE = timedelta(days=7)
_SIGNATURE_LENGTH = 32


def base_url() -> str | None:
    base = (settings.email_asset_base_url or "").strip().rstrip("/")
    return base or None


def logo_url() -> str | None:
    base = base_url()
    return f"{base}{EMAIL_ASSETS_PATH}/{LOGO_FILENAME}" if base else None


def _secret() -> bytes:
    secret = (
        settings.email_asset_url_secret
        or settings.storage_local_url_secret
        or settings.jwt_secret_key
    )
    return secret.encode()


def _signature(tenant_id: uuid.UUID, invitation_id: uuid.UUID, expires: int) -> str:
    message = f"qr:{tenant_id}:{invitation_id}:{expires}".encode()
    return hmac.new(_secret(), message, hashlib.sha256).hexdigest()[:_SIGNATURE_LENGTH]


def qr_url_expiry(visit_expires_at: datetime) -> int:
    return int((visit_expires_at + QR_URL_GRACE).timestamp())


def sign_qr_url(
    tenant_id: uuid.UUID, invitation_id: uuid.UUID, visit_expires_at: datetime
) -> str | None:
    """`None` when no base URL is configured — the caller then embeds the
    QR inline instead (the fallback).
    """
    base = base_url()
    if base is None:
        return None
    expires = qr_url_expiry(visit_expires_at)
    query = urlencode({"exp": expires, "sig": _signature(tenant_id, invitation_id, expires)})
    return f"{base}{EMAIL_ASSETS_PATH}/{tenant_id}/qr/{invitation_id}.png?{query}"


def verify_qr_signature(
    tenant_id: uuid.UUID, invitation_id: uuid.UUID, expires: int, signature: str
) -> bool:
    return hmac.compare_digest(_signature(tenant_id, invitation_id, expires), signature)


def is_expired(expires: int) -> bool:
    return expires < int(time.time())
