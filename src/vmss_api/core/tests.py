import io
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core import encryption, storage
from vmss_api.core.config import settings
from vmss_api.core.tenancy import DefaultTenantUnresolved, resolve_default_tenant
from vmss_api.main import create_app
from vmss_api.tenant.models import Tenant


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


# --- environment-configuration capability: shared default-tenant resolver ----
#
# `resolve_default_tenant` (`core/tenancy.py`) is the single lookup behind
# every public endpoint that falls back to `settings.default_tenant_slug`
# (`registrations`, `identity_verification`, `invitations`' tracking lookup —
# see harden-default-tenant-resolution-and-readiness/design.md). It raises
# `DefaultTenantUnresolved` rather than an `HTTPException` so each caller
# keeps its own status code/message; these tests cover the resolver itself,
# not any one caller's translation of it.


async def test_resolve_default_tenant_resolves_active_tenant(
    db_session: AsyncSession, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)

    resolved = await resolve_default_tenant(db_session)

    assert resolved.id == tenant.id


async def test_resolve_default_tenant_raises_not_found_for_unknown_slug(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "no-such-tenant-slug")

    with pytest.raises(DefaultTenantUnresolved) as exc_info:
        await resolve_default_tenant(db_session)

    assert exc_info.value.reason == "not_found"


async def test_resolve_default_tenant_raises_inactive_for_inactive_tenant(
    db_session: AsyncSession, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)
    await db_session.execute(update(Tenant).where(Tenant.id == tenant.id).values(is_active=False))
    await db_session.commit()

    with pytest.raises(DefaultTenantUnresolved) as exc_info:
        await resolve_default_tenant(db_session)

    assert exc_info.value.reason == "inactive"


# --- encryption (API-19, add-sso-oidc-login) ----------------------------------


def test_encrypt_decrypt_round_trips(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sso_encryption_key", Fernet.generate_key().decode())
    encryption._fernet.cache_clear()

    ciphertext = encryption.encrypt("super-secret-value")
    assert ciphertext != "super-secret-value"
    assert encryption.decrypt(ciphertext) == "super-secret-value"


def test_decrypt_tampered_ciphertext_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sso_encryption_key", Fernet.generate_key().decode())
    encryption._fernet.cache_clear()

    ciphertext = encryption.encrypt("super-secret-value")
    tampered = ciphertext[:-4] + ("A" if ciphertext[-4] != "A" else "B") + ciphertext[-3:]

    with pytest.raises(ValueError):
        encryption.decrypt(tampered)


def test_decrypt_with_a_different_key_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sso_encryption_key", Fernet.generate_key().decode())
    encryption._fernet.cache_clear()
    ciphertext = encryption.encrypt("super-secret-value")

    monkeypatch.setattr(settings, "sso_encryption_key", Fernet.generate_key().decode())
    encryption._fernet.cache_clear()

    with pytest.raises(ValueError):
        encryption.decrypt(ciphertext)


def test_encrypt_without_key_configured_raises_loudly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sso_encryption_key", None)
    encryption._fernet.cache_clear()

    with pytest.raises(encryption.EncryptionKeyNotConfigured):
        encryption.encrypt("anything")


def test_mask_secret_keeps_only_the_last_four_characters() -> None:
    assert encryption.mask_secret("abcd1234wxyz") == "****wxyz"
    assert encryption.mask_secret("ab") == "****ab"


# --- environment-configuration capability: debug-mode safety and exception
# leak hardening (fix-unhandled-exception-leak) ------------------------------
#
# `RequestIdMiddleware` used to subclass Starlette's `BaseHTTPMiddleware`,
# which can let an exception raised downstream bypass the app's registered
# exception handlers — that's how a production request once returned a raw
# framework traceback instead of the standard error envelope. These tests
# build a fresh app via the real `create_app()` wiring (not the module-level
# `app` singleton) so `settings.environment`/`settings.debug` can vary per
# case, and add a route that unconditionally raises to prove the envelope
# is what a client actually receives end-to-end.


@pytest.mark.parametrize(
    ("environment", "debug"),
    [
        ("production", True),
        ("staging", True),
        ("local", True),
        ("testing", True),
        ("production", False),
    ],
)
def test_effective_debug_is_only_true_in_local_or_testing(
    monkeypatch, environment: str, debug: bool
) -> None:
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "debug", debug)

    assert settings.effective_debug == (debug and environment in {"local", "testing"})


_STANDARD_ERROR_ENVELOPE = {
    "success": False,
    "message": "An unexpected error occurred.",
    "errors": None,
}


async def test_unhandled_exception_in_a_route_returns_standard_envelope_when_debug_disabled(
    monkeypatch,
) -> None:
    """Reproduces the reported incident with debug mode disabled — the state
    every real `staging`/`production` deployment is forced into by
    `effective_debug`. `ASGITransport`'s default `raise_app_exceptions=True`
    re-raises the exception Starlette's `ServerErrorMiddleware` itself
    always re-raises after already sending the response (see design.md's
    Context) — `raise_app_exceptions=False` lets this test inspect that
    already-sent response instead of the re-raise.
    """
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    test_app = create_app("production")

    @test_app.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test/boom")

    assert response.status_code == 500
    assert response.json() == _STANDARD_ERROR_ENVELOPE
    assert "boom" not in response.text
    assert "Traceback" not in response.text
    assert "vmss_api" not in response.text


async def test_unhandled_exception_in_middleware_returns_standard_envelope_when_debug_disabled(
    monkeypatch,
) -> None:
    """Same as above, but the exception originates ahead of routing —
    proving the standard envelope isn't just a route-handler-specific
    behavior (`unhandled_exception_handler` is reached the same way
    regardless of where in the stack the exception is raised).
    """
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    test_app = create_app("production")

    class _AlwaysRaisesMiddleware:
        def __init__(self, app) -> None:
            self.app = app

        async def __call__(self, scope, receive, send) -> None:
            raise RuntimeError("boom-in-middleware")

    test_app.add_middleware(_AlwaysRaisesMiddleware)

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 500
    assert response.json() == _STANDARD_ERROR_ENVELOPE
    assert "boom-in-middleware" not in response.text
    assert "Traceback" not in response.text
