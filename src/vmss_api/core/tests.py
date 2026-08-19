import io
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from PIL import Image

from vmss_api.core import storage
from vmss_api.core.config import settings


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


# --- file-storage capability: content/size validation (backend-independent) --


def test_validate_upload_rejects_disguised_content() -> None:
    with pytest.raises(storage.UnsupportedFileTypeError):
        storage.validate_upload(b"not actually an image", max_size_bytes=1_000_000)


def test_validate_upload_rejects_oversized_content() -> None:
    with pytest.raises(storage.FileTooLargeError):
        storage.validate_upload(_png_bytes(), max_size_bytes=1)


def test_validate_upload_accepts_allow_listed_content() -> None:
    content_type = storage.validate_upload(_png_bytes(), max_size_bytes=1_000_000)
    assert content_type == "image/png"


# --- file-storage capability: local backend -----------------------------------


async def test_local_backend_save_and_url_for_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "storage_root", str(tmp_path))
    content = _png_bytes()

    key = await storage.save(uuid.uuid4(), "tests/photo", content, "image/png")
    path = await storage.url_for(key)

    assert Path(path).read_bytes() == content


# --- file-storage capability: S3-compatible backend (API-14) ------------------
#
# A real `moto`+`aioboto3` round-trip hits a documented incompatibility
# between moto's in-process response stubbing and aiobotocore's async body
# handling (`TypeError: object bytes can't be used in 'await' expression'),
# not anything in this project's own code — moto's server mode fixes it but
# needs `flask`, an extra dependency this project has no other use for.
# Faking the boundary (`storage._s3_client`) instead proves our own
# save/url_for wiring (bucket, key, body, content-type all passed through
# correctly) — the same "fake the external boundary" approach
# `invitations/tests.py`'s `_fake_tenant_session_scope` already uses for
# Celery task tests.


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    async def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[(Bucket, Key)] = (Body, ContentType)

    async def get_object(self, *, Bucket: str, Key: str) -> dict:
        body, content_type = self.objects[(Bucket, Key)]

        class _Body:
            async def read(self_inner) -> bytes:
                return body

        return {"Body": _Body(), "ContentType": content_type}

    async def generate_presigned_url(self, _operation: str, *, Params: dict, ExpiresIn: int) -> str:
        return f"https://{Params['Bucket']}.example.com/{Params['Key']}?ttl={ExpiresIn}"


def _install_fake_s3_client(monkeypatch) -> _FakeS3Client:
    fake_client = _FakeS3Client()

    @asynccontextmanager
    async def _fake_s3_client():
        yield fake_client

    monkeypatch.setattr(storage, "_s3_client", _fake_s3_client)
    return fake_client


async def test_s3_backend_save_and_retrieve_round_trip(monkeypatch) -> None:
    bucket = "vmss-test-bucket"
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", bucket)
    fake_client = _install_fake_s3_client(monkeypatch)

    content = _png_bytes()
    key = await storage.save(uuid.uuid4(), "tests/photo", content, "image/png")

    stored_body, stored_content_type = fake_client.objects[(bucket, key)]
    assert stored_body == content
    assert stored_content_type == "image/png"

    url = await storage.url_for(key)
    assert bucket in url
    assert key in url


async def test_s3_backend_misconfigured_bucket_raises_storage_backend_error(monkeypatch) -> None:
    """spec.md "Backend unreachable or misconfigured" — a save is rejected
    explicitly, never silently dropped.
    """
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", None)

    with pytest.raises(storage.StorageBackendError):
        await storage.save(uuid.uuid4(), "tests/photo", _png_bytes(), "image/png")
