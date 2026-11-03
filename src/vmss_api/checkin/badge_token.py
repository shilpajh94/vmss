"""Signed, day-bound badge QR tokens (add-badge-print-flow design Decision 7).

PyJWT HS256 keyed by a domain-separated HMAC of `settings.jwt_secret_key`, so
the signing key is never the raw JWT key and no extra env secret is needed.
Claims: `sub` (visit id), `tid` (tenant id), `day` (tenant-local ISO date the
badge is valid for), `jti` (matches `badge_prints.jti`), `typ="badge"`, `exp`.

`verify_badge_token` returns `None` for every failure mode (tampered, expired,
wrong type, malformed) so callers can answer with one generic response without
revealing which check failed — same contract as
`invitations/qr_token.py::decrypt_invitation_token`. Whether the `jti` is still
active, and whether `day` is today, are checked by the service against the DB
and the tenant's clock; this module only proves the token is ours and intact.
"""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import jwt

from vmss_api.core.config import settings

_ALGORITHM = "HS256"
_TYPE = "badge"
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


def issue_badge_token(
    *, visit_id: uuid.UUID, tenant_id: uuid.UUID, day: date, jti: str, timezone: str
) -> str:
    """`exp` is the end of `day` in the tenant's timezone plus a small grace,
    so the token is dead on its own even if the DB row were never deactivated.
    """
    end_of_day = datetime.combine(day + timedelta(days=1), time.min, tzinfo=ZoneInfo(timezone))
    payload = {
        "sub": str(visit_id),
        "tid": str(tenant_id),
        "day": day.isoformat(),
        "jti": jti,
        "typ": _TYPE,
        "exp": (end_of_day + _EXPIRY_GRACE).astimezone(UTC),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def verify_badge_token(token: str) -> BadgeClaims | None:
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub", "tid", "day", "jti", "typ"]},
        )
        if payload["typ"] != _TYPE:
            return None
        return BadgeClaims(
            visit_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tid"]),
            day=date.fromisoformat(payload["day"]),
            jti=str(payload["jti"]),
        )
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        return None
