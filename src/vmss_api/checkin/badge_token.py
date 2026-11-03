"""Signed, day-bound badge QR tokens (add-badge-print-flow design Decision 7).

A compact binary token, not a JWT: the token is drawn into a QR code, and a
324-char JWT made a QR too dense to scan reliably. Layout (then base64url,
no padding, ~118 chars):

    version(1) | visit_id(16) | tenant_id(16) | day ordinal(4) | exp(4)
             | jti(16 if 32-hex, else raw utf-8) | HMAC-SHA256[:16]

The HMAC key is a domain-separated derivation of `settings.jwt_secret_key`,
so the signing key is never the raw JWT key and no extra env secret is needed.
Claims are the same as before: visit id, tenant id, `day` (tenant-local date
the badge is valid for), `jti` (matches `badge_prints.jti`) and `exp`.

`verify_badge_token` returns `None` for every failure mode (tampered, expired,
wrong type, malformed) so callers can answer with one generic response without
revealing which check failed — same contract as
`invitations/qr_token.py::decrypt_invitation_token`. Whether the `jti` is still
active, and whether `day` is today, are checked by the service against the DB
and the tenant's clock; this module only proves the token is ours and intact.
"""

import base64
import hashlib
import hmac
import struct
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from vmss_api.core.config import settings

_V_HEX_JTI = 1
_V_RAW_JTI = 2
_MAC_LEN = 16
_FIXED = struct.Struct(">B16s16sII")
_EXPIRY_GRACE = timedelta(hours=1)


@dataclass(frozen=True)
class BadgeClaims:
    visit_id: uuid.UUID
    tenant_id: uuid.UUID
    day: date
    jti: str


def _secret() -> bytes:
    return hmac.new(
        settings.jwt_secret_key.encode(), b"vmss:badge-token:v1", hashlib.sha256
    ).digest()


def new_jti() -> str:
    return uuid.uuid4().hex


def _mac(body: bytes) -> bytes:
    return hmac.new(_secret(), body, hashlib.sha256).digest()[:_MAC_LEN]


def issue_badge_token(
    *, visit_id: uuid.UUID, tenant_id: uuid.UUID, day: date, jti: str, timezone: str
) -> str:
    """`exp` is the end of `day` in the tenant's timezone plus a small grace,
    so the token is dead on its own even if the DB row were never deactivated.
    """
    end_of_day = datetime.combine(day + timedelta(days=1), time.min, tzinfo=ZoneInfo(timezone))
    exp = int((end_of_day + _EXPIRY_GRACE).astimezone(UTC).timestamp())
    try:
        jti_bytes, version = bytes.fromhex(jti), _V_HEX_JTI
        if len(jti_bytes) != 16 or jti_bytes.hex() != jti.lower():
            raise ValueError
    except ValueError:
        jti_bytes, version = jti.encode(), _V_RAW_JTI
    body = _FIXED.pack(version, visit_id.bytes, tenant_id.bytes, day.toordinal(), exp) + jti_bytes
    return base64.urlsafe_b64encode(body + _mac(body)).rstrip(b"=").decode()


def verify_badge_token(token: str) -> BadgeClaims | None:
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        if len(raw) < _FIXED.size + _MAC_LEN:
            return None
        body, mac = raw[:-_MAC_LEN], raw[-_MAC_LEN:]
        if not hmac.compare_digest(mac, _mac(body)):
            return None
        version, visit_raw, tenant_raw, ordinal, exp = _FIXED.unpack_from(body)
        if exp < datetime.now(UTC).timestamp():
            return None
        rest = body[_FIXED.size :]
        if version == _V_HEX_JTI:
            jti = rest.hex()
        elif version == _V_RAW_JTI:
            jti = rest.decode()
        else:
            return None
        return BadgeClaims(
            visit_id=uuid.UUID(bytes=visit_raw),
            tenant_id=uuid.UUID(bytes=tenant_raw),
            day=date.fromordinal(ordinal),
            jti=jti,
        )
    except (ValueError, struct.error, UnicodeDecodeError, TypeError):
        return None
