import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status

from vmss_api.core.config import settings

_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, raw_password)
    except VerifyMismatchError:
        return False


def _create_token(
    subject: uuid.UUID, tenant_id: uuid.UUID | None, expires_delta: timedelta, token_type: str
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: uuid.UUID, tenant_id: uuid.UUID) -> str:
    return _create_token(
        subject, tenant_id, timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(subject: uuid.UUID, tenant_id: uuid.UUID) -> str:
    expires_delta = timedelta(minutes=settings.refresh_token_expire_minutes)
    return _create_token(subject, tenant_id, expires_delta, "refresh")


def create_platform_access_token(subject: uuid.UUID) -> str:
    """Superadmin tokens carry no `tenant_id` claim — a superadmin isn't a
    member of any tenant's schema. See `platform/service.py`.
    """
    return _create_token(
        subject, None, timedelta(minutes=settings.access_token_expire_minutes), "platform_access"
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc
