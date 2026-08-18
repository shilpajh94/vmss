"""Minimal file-storage interface (database-architecture.md §1): local disk
in dev, an S3-compatible client behind the same two functions in prod. First
feature to need it is `invitations` (ID-proof uploads) — see
openspec/changes/add-pre-registration/design.md Decision 3.
"""

import uuid
from pathlib import Path

import anyio
import magic

from vmss_api.core.config import settings

# Allow-list per file-upload-handling.md §2 — checked against the file's real
# content, never the client-supplied Content-Type header or filename
# extension.
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}


class UnsupportedFileTypeError(ValueError):
    """Raised when an upload's real content isn't in the allow-list."""


class FileTooLargeError(ValueError):
    """Raised when an upload exceeds `settings.invitation_max_upload_size_bytes`."""


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


async def save(tenant_id: uuid.UUID, category: str, content: bytes, content_type: str) -> str:
    """Persists `content` and returns a storage key following the
    `vmss:{tenant_id}:{feature}:{entity}:{id}` convention
    (database-architecture.md §6). The key, not a raw path, is what callers
    store and pass to `url_for` — swapping the body of this function for an
    S3-compatible client later doesn't change any call site.
    """
    extension = _ALLOWED_CONTENT_TYPES[content_type]
    key = f"vmss:{tenant_id}:{category}:{uuid.uuid4()}{extension}"
    await anyio.to_thread.run_sync(_write_file, _path_for(key), content)
    return key


async def url_for(key: str) -> str:
    return str(_path_for(key))


def _path_for(key: str) -> Path:
    return Path(settings.storage_root, *key.split(":"))
