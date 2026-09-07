"""Minimal file-storage interface (database-architecture.md §1): local disk
in dev, an S3-compatible client behind the same two functions in prod. First
feature to need it is `invitations` (ID-proof uploads) — see
openspec/changes/add-pre-registration/design.md Decision 3. The S3-compatible
backend (API-14) is selected by `settings.storage_backend` — see
add-walkin-visitor-registration/design.md Decision 4; callers never branch on
which backend is active, they only ever handle the opaque key `save` returns.
"""

import hashlib
import hmac
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import aioboto3
import anyio
import magic
from botocore.exceptions import BotoCoreError, ClientError

from vmss_api.core.config import settings

# Allow-list per file-upload-handling.md §2 — checked against the file's real
# content, never the client-supplied Content-Type header or filename
# extension.
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}

# Extensions `save()` accepts in addition to `_ALLOWED_CONTENT_TYPES`, for
# server-generated files (e.g. `audit_trail`'s CSV report export) that never
# pass through `validate_upload` — kept separate from the allow-list above so
# a client upload still can't smuggle a CSV in as an "ID proof" file; only
# `save()`'s extension lookup is widened, not what `validate_upload` accepts.
_GENERATED_FILE_EXTENSIONS = {
    "text/csv": ".csv",
}


class UnsupportedFileTypeError(ValueError):
    """Raised when an upload's real content isn't in the allow-list."""


class FileTooLargeError(ValueError):
    """Raised when an upload exceeds `settings.invitation_max_upload_size_bytes`."""


class StorageBackendError(RuntimeError):
    """Raised when the configured storage backend can't complete an
    operation — unreachable endpoint, missing bucket, bad credentials.
    Surfaced as an explicit failure rather than a silently-lost upload
    (file-storage capability spec.md "Backend unreachable or
    misconfigured").
    """


def _local_url_secret() -> bytes:
    secret = settings.storage_local_url_secret or settings.jwt_secret_key
    return secret.encode("utf-8")


def _local_url_signature(key: str, expires_at: int) -> str:
    message = f"{key}:{expires_at}".encode()
    return hmac.new(_local_url_secret(), message, hashlib.sha256).hexdigest()


async def _local_presigned_url(key: str) -> str:
    """Signed, time-boxed URL for the `local` backend, mirroring the `s3`
    backend's presigned-URL model (add-avatar-upload-and-verify-image-
    storage/design.md Decision 1) — the signature is the authorization, a
    caller fetching it needs no separate permission check.
    """
    expires_at = int(time.time()) + settings.storage_local_presigned_url_ttl_seconds
    signature = _local_url_signature(key, expires_at)
    return f"/api/v1/files/local/{quote(key, safe='')}?exp={expires_at}&sig={signature}"


def verify_local_url(key: str, expires_at: int, signature: str) -> bool:
    """Verifies a local-backend signed URL's signature and expiry. Returns
    `False` on tamper or expiry rather than raising, so the serving route can
    respond with a uniform rejection regardless of which check failed.
    """
    if expires_at < int(time.time()):
        return False
    expected = _local_url_signature(key, expires_at)
    return hmac.compare_digest(expected, signature)


_s3_session = aioboto3.Session()


@asynccontextmanager
async def _s3_client():
    if not settings.storage_s3_bucket:
        raise StorageBackendError("storage_s3_bucket is not configured")
    async with _s3_session.client(
        "s3",
        region_name=settings.storage_s3_region,
        endpoint_url=settings.storage_s3_endpoint_url,
    ) as client:
        yield client


def validate_upload(content: bytes, *, max_size_bytes: int) -> str:
    """Validates real content (magic-byte sniffing via `python-magic`, not
    the client's declared content type or the filename extension — a renamed
    `.exe` with a spoofed `Content-Type: image/jpeg` is the standard bypass
    for extension/header-only checks) and size. Returns the sniffed content
    type on success.
    """
    if len(content) > max_size_bytes:
        raise FileTooLargeError(f"File exceeds the {max_size_bytes}-byte limit")
    content_type = magic.from_buffer(content, mime=True)
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported file type: {content_type!r}")
    return content_type


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _read_file(path: Path) -> bytes:
    return path.read_bytes()


async def save(tenant_id: uuid.UUID, category: str, content: bytes, content_type: str) -> str:
    """Persists `content` and returns a storage key following the
    `vmss:{tenant_id}:{feature}:{entity}:{id}` convention
    (database-architecture.md §6). The key, not a raw path, is what callers
    store and pass to `url_for` — which physical backend actually persisted
    it (`settings.storage_backend`) is invisible from here on.
    """
    extension = {**_ALLOWED_CONTENT_TYPES, **_GENERATED_FILE_EXTENSIONS}[content_type]
    key = f"vmss:{tenant_id}:{category}:{uuid.uuid4()}{extension}"
    if settings.storage_backend == "s3":
        await _s3_save(key, content, content_type)
    else:
        await anyio.to_thread.run_sync(_write_file, _path_for(key), content)
    return key


async def url_for(key: str) -> str:
    """A client-fetchable, pre-signed, time-boxed URL for `key` — via S3's
    own presigned-URL mechanism for the `s3` backend, via a locally signed
    URL served by `core/storage_router.py` for `local`
    (add-avatar-upload-and-verify-image-storage/design.md Decision 1). Either
    way, the caller never branches on which backend produced it, and the
    result is always safe to place directly in a client-facing response
    field — never a raw server-side filesystem path.
    """
    if settings.storage_backend == "s3":
        return await _s3_presigned_url(key)
    return await _local_presigned_url(key)


async def load(key: str) -> bytes:
    """Reads back the raw bytes stored under `key`, for a caller that serves
    content itself from behind its own check rather than handing out a
    `url_for` reference — used by `audit_trail`'s report download and by
    `core/storage_router.py`'s local-URL-serving route.
    """
    if settings.storage_backend == "s3":
        return await _s3_load(key)
    return await anyio.to_thread.run_sync(_read_file, _path_for(key))


def content_type_for(key: str) -> str:
    """Recovers the content type `save()` stored `key` under, from its file
    extension — the allow-list/generated-extension maps are small and
    1:1, so this is just the reverse lookup of the map `save()` used.
    """
    extension = Path(key).suffix
    all_types = {**_ALLOWED_CONTENT_TYPES, **_GENERATED_FILE_EXTENSIONS}
    by_extension = {v: k for k, v in all_types.items()}
    return by_extension[extension]


async def _s3_save(key: str, content: bytes, content_type: str) -> None:
    try:
        async with _s3_client() as client:
            await client.put_object(
                Bucket=settings.storage_s3_bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
    except (BotoCoreError, ClientError) as exc:
        raise StorageBackendError(f"Failed to save {key!r} to S3: {exc}") from exc


async def _s3_load(key: str) -> bytes:
    try:
        async with _s3_client() as client:
            response = await client.get_object(Bucket=settings.storage_s3_bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()
    except (BotoCoreError, ClientError) as exc:
        raise StorageBackendError(f"Failed to load {key!r} from S3: {exc}") from exc


async def _s3_presigned_url(key: str) -> str:
    try:
        async with _s3_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.storage_s3_bucket, "Key": key},
                ExpiresIn=settings.storage_s3_presigned_url_ttl_seconds,
            )
    except (BotoCoreError, ClientError) as exc:
        raise StorageBackendError(f"Failed to generate a URL for {key!r}: {exc}") from exc


def _path_for(key: str) -> Path:
    return Path(settings.storage_root, *key.split(":"))
