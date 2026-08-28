"""Symmetric encryption for a secret that must later be *recovered* in
plaintext (e.g. an SSO client secret used to call an IdP's token endpoint) —
unlike `core/security.py`'s Argon2 password hashing, which is one-way and
can only verify, never decrypt. General infrastructure, not `sso`-specific:
the next feature needing the same guarantee (an SMTP relay password, a
webhook signing secret) reuses this instead of inventing its own scheme.
See `openspec/changes/add-sso-oidc-login/design.md`'s
"`core/encryption.py`: Fernet, not a per-feature ad hoc scheme" decision.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from vmss_api.core.config import settings


class EncryptionKeyNotConfigured(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    if not settings.sso_encryption_key:
        raise EncryptionKeyNotConfigured(
            "SSO_ENCRYPTION_KEY is not set — generate one with "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and set it before '
            "encrypting or decrypting any secret."
        )
    return Fernet(settings.sso_encryption_key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Ciphertext is invalid, corrupted, or was encrypted with a different key"
        ) from exc


def mask_secret(plaintext: str) -> str:
    """`****1234` — the last 4 characters only, for display after the
    secret has been saved. Callers must derive this from the plaintext at
    write time (or decrypt once to compute it) rather than ever decrypting
    on every read just to mask it.
    """
    tail = plaintext[-4:] if len(plaintext) >= 4 else plaintext
    return f"****{tail}"
