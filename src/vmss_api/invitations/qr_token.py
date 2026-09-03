"""Encrypted QR check-in tokens (`add-qr-checkin-security/design.md`).

Mirrors `core/encryption.py`'s Fernet-based "encrypt now, decrypt later"
pattern rather than a bespoke crypto primitive — Fernet already gives
tamper detection (`InvalidToken` on any modified token) and URL-safe
output with no extra encoding step. Deliberately keyed by its own
`settings.qr_token_encryption_key`, not the existing `sso_encryption_key`:
rotating one secret shouldn't silently invalidate the other.
"""

import uuid
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from vmss_api.core.config import settings


class QrTokenEncryptionKeyNotConfigured(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    if not settings.qr_token_encryption_key:
        raise QrTokenEncryptionKeyNotConfigured(
            "QR_TOKEN_ENCRYPTION_KEY is not set — generate one with "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and set it before '
            "generating or verifying any QR check-in token."
        )
    return Fernet(settings.qr_token_encryption_key)


def encrypt_invitation_token(invitation_id: uuid.UUID) -> str:
    return _fernet().encrypt(str(invitation_id).encode("utf-8")).decode("utf-8")


def decrypt_invitation_token(token: str) -> uuid.UUID | None:
    """`None` for anything that isn't a currently-valid token for this key —
    tampered, expired-format, or simply malformed input — never raises, so
    callers (the public check-in endpoint) can treat every failure mode as
    one flat "invalid token" response without revealing which part failed.
    """
    try:
        plaintext = _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
        return uuid.UUID(plaintext)
    except (InvalidToken, ValueError):
        return None
