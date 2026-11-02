import warnings
from functools import lru_cache
from typing import Literal, Self
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `DB_CONNECTION` mirrors the Laravel-style env var convention this project's
# `.env` layout follows; the mapping has exactly one entry today because this
# project is Postgres-only (project-rules.md) — it exists for naming
# consistency, not to imply multi-driver support.
_DB_DRIVERS: dict[str, str] = {"pgsql": "postgresql+asyncpg"}

# The product name shown to people: email From name, footers, alt text.
# One constant so a rename is a one-line change (rebrand-to-guestify).
BRAND_NAME = "Guestify"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = f"{BRAND_NAME} API"
    environment: str = Field(default="local", alias="APP_ENV")
    # Comma-separated addresses/CIDRs of the load balancer or reverse proxy
    # whose X-Forwarded-For is trusted for the client IP (rate-limit keys,
    # logs). Default trusts only a same-host proxy; "*" trusts everyone.
    forwarded_allow_ips: str = Field(default="127.0.0.1", alias="FORWARDED_ALLOW_IPS")
    # public-endpoint-hardening: off keeps today's unauthenticated contracts
    # (flagged as deprecated); on enforces the credentials each covered
    # endpoint will require. Turn on once the Flutter/kiosk clients migrate.
    public_endpoint_hardening: bool = Field(default=False, alias="PUBLIC_ENDPOINT_HARDENING")
    debug: bool = Field(default=True, alias="APP_DEBUG")

    @property
    def effective_debug(self) -> bool:
        """Gates FastAPI's debug behavior (verbose tracebacks on an
        unhandled exception) — `APP_DEBUG` alone is never trusted for this,
        so a deployment that forgets to set `APP_DEBUG=false` can't leak a
        debug traceback in `staging`/`production`. `debug` itself is left
        untouched for its other use (`configure_logging`'s verbosity gate).
        """
        return self.debug and self.environment.lower() in {"local", "testing"}

    # `core/logging.py` — minimum level to emit; production-safe default so
    # verbosity is raised per-environment without a code change
    # (logging-observability.md §3).
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database — component vars are assembled into the SQLAlchemy async DSN
    # `database_url` below. No component defaults to a value that resolves
    # to a real target (`None`, not a hardcoded host) — so an environment
    # that sets neither the components nor `DATABASE_URL` fails at
    # `database_url` access time with a clear missing-setting error, instead
    # of silently reaching a hardcoded host. If `DATABASE_URL` is set (e.g. a
    # PaaS that injects one connection string at deploy time), it wins
    # outright and none of the components need to be set at all.
    db_connection: Literal["pgsql"] = Field(default="pgsql", alias="DB_CONNECTION")
    db_host: str | None = Field(default=None, alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_database: str | None = Field(default=None, alias="DB_NAME")
    db_username: str | None = Field(default=None, alias="DB_USER")
    db_password: str | None = Field(default=None, alias="DB_PASSWORD")
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    db_pool_size: int = Field(default=20, ge=1, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, ge=0, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, ge=1, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, ge=-1, alias="DB_POOL_RECYCLE")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        missing = [
            name
            for name, value in (
                ("DB_HOST", self.db_host),
                ("DB_NAME", self.db_database),
                ("DB_USER", self.db_username),
                ("DB_PASSWORD", self.db_password),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"Database is not configured: set DATABASE_URL, or all of {', '.join(missing)}."
            )
        assert self.db_username is not None and self.db_password is not None  # validated above
        driver = _DB_DRIVERS[self.db_connection]
        return (
            f"{driver}://"
            f"{quote_plus(self.db_username)}:"
            f"{quote_plus(self.db_password)}@"
            f"{self.db_host}:{self.db_port}/"
            f"{self.db_database}"
        )

    # Redis — one instance, one logical DB index per purpose (cache, Celery
    # broker, Celery result backend), same override-if-set precedence as the
    # database above. `redis_host` defaults to `None` for the same
    # no-hardcoded-connection-target reason as `db_host`.
    redis_host: str | None = Field(default=None, alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str | None = Field(default=None, alias="REDIS_PASSWORD")
    redis_cache_db: int = Field(default=0, alias="REDIS_CACHE_DB")
    redis_celery_broker_db: int = Field(default=1, alias="REDIS_CELERY_BROKER_DB")
    redis_celery_result_db: int = Field(default=2, alias="REDIS_CELERY_RESULT_DB")
    redis_url_override: str | None = Field(default=None, alias="REDIS_URL")
    celery_broker_url_override: str | None = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend_override: str | None = Field(default=None, alias="CELERY_RESULT_BACKEND")

    def _redis_url(self, override: str | None, db_index: int) -> str:
        if override:
            return override
        if not self.redis_host:
            raise ValueError(
                "Redis is not configured: set REDIS_HOST (plus REDIS_PORT/"
                "REDIS_PASSWORD as needed), or the specific *_URL override."
            )
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{db_index}"

    @property
    def redis_url(self) -> str:
        return self._redis_url(self.redis_url_override, self.redis_cache_db)

    @property
    def celery_broker_url(self) -> str:
        return self._redis_url(self.celery_broker_url_override, self.redis_celery_broker_db)

    @property
    def celery_result_backend(self) -> str:
        return self._redis_url(self.celery_result_backend_override, self.redis_celery_result_db)

    jwt_secret_key: str = "change-me-in-env"
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(
        default=60 * 24 * 7, alias="JWT_REFRESH_TOKEN_EXPIRE_MINUTES"
    )

    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # The Postgres schema holding cross-tenant registry tables (tenants,
    # superadmins, the auth index, ...). Every tenant gets its own
    # `{tenant_schema_prefix}{slug}` schema — see database-architecture.md §2.
    default_tenant_slug: str = Field(default="default", alias="TENANT_DEFAULT_SLUG")
    global_schema_name: str = Field(default="global", alias="TENANT_GLOBAL_SCHEMA_NAME")
    tenant_schema_prefix: str = "tenant_"

    # `core/storage.py` — local-disk-backed in dev, per database-architecture.md
    # §1. `storage_backend` selects the implementation behind the same
    # `save`/`url_for` interface (API-14,
    # add-walkin-visitor-registration/design.md Decision 4) — switching it is
    # a config change, never a call-site change. `AWS_ACCESS_KEY_ID`/
    # `AWS_SECRET_ACCESS_KEY` are not Settings fields: boto3's default
    # credential provider chain reads them directly from the process
    # environment (see `.env.example`).
    storage_root: str = "./var/storage"

    # "local" (default, disk-backed) or "s3" (API-14) — selects which branch
    # of `core/storage.py` handles save/url_for. The three `storage_s3_*`
    # fields below are only read on the "s3" branch and use their default
    # (unaliased) `STORAGE_S3_*` env var names — see `.env.example`. AWS
    # credentials themselves are read by boto3's own default credential
    # provider chain (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/
    # `AWS_DEFAULT_REGION`), not through `Settings`.
    storage_backend: Literal["local", "s3"] = "local"
    storage_s3_bucket: str | None = None
    storage_s3_region: str | None = None
    # Only needed for a non-AWS S3-compatible provider (e.g. MinIO); leave
    # unset to use AWS's default endpoint resolution.
    storage_s3_endpoint_url: str | None = None
    # How long a `url_for` pre-signed URL stays valid when `storage_backend`
    # is "s3" — irrelevant for "local", which returns a plain path.
    storage_s3_presigned_url_ttl_seconds: int = 300

    # Signs a fetchable URL for the "local" backend (add-avatar-upload-and-
    # verify-image-storage) — falls back to `jwt_secret_key` when left
    # genuinely blank, but every real environment should set a dedicated
    # value (see `.env.example`).
    storage_local_url_secret: str | None = None
    storage_local_presigned_url_ttl_seconds: int = 300
    storage_public_base_url: str | None = Field(
        default=None,
        alias="STORAGE_PUBLIC_BASE_URL",
    )

    # Mail settings for `core/emailing.py`'s `SmtpEmailSender` — shared by
    # `invitations/notifications.py` and `reports/tasks.py` (see
    # add-pre-registration/design.md Decision 4 and
    # add-background-jobs-and-integration-tests/design.md Decision 4).
    # Defaults point at a local dev mail-catcher (e.g. mailhog/mailpit) so a
    # fresh checkout doesn't need a real mail server to send/queue without
    # erroring.
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=False, alias="SMTP_USE_TLS")
    smtp_from_address: str = Field(default="no-reply@vmss.local", alias="SMTP_FROM_ADDRESS")
    # Display name shown in front of `smtp_from_address` ("Guestify <no-reply@…>").
    smtp_from_name: str = Field(default=BRAND_NAME, alias="SMTP_FROM_NAME")
    # Public origin email `<img src>` URLs are built from — the Guestify logo
    # and the signed check-in QR (`core/email_assets.py`). Unset means
    # emails fall back to a text wordmark and an inline `cid:` QR.
    email_asset_base_url: str | None = Field(default=None, alias="EMAIL_ASSET_BASE_URL")
    # Signs QR image URLs; falls back to `storage_local_url_secret`, then
    # `jwt_secret_key`, when unset.
    email_asset_url_secret: str | None = Field(default=None, alias="EMAIL_ASSET_URL_SECRET")
    # Public origin of the web app (VMMS_WEB) that notification-email
    # call-to-action links point into (`core/portal_links.py`) — despite the
    # name, visitor links use it too. Supplied per environment through the
    # `__STAFF_PORTAL_URL__` pipeline token; unset (or an unreplaced token)
    # means emails carry no link.
    staff_portal_url: str | None = Field(default=None, alias="STAFF_PORTAL_URL")

    # Fast2SMS — DLT SMS (`core/sms.py`) and WhatsApp (`core/whatsapp.py`) for
    # identity-verification OTP and invitation notifications. All optional:
    # a blank value means "not configured" and the sender fails loudly per
    # call (background-jobs.md §4) instead of pretending to send.
    fast2sms_api_key: str | None = None
    fast2sms_sender_id: str | None = None
    fast2sms_base_url: str = "https://www.fast2sms.com"
    # DLT-approved template IDs, one per SMS message type.
    fast2sms_template_otp: str | None = None
    fast2sms_template_registration_pending: str | None = None
    fast2sms_template_registration_confirmed: str | None = None
    fast2sms_template_registration_confirmed_code: str | None = None
    fast2sms_template_registration_denied: str | None = None
    fast2sms_template_visit_rescheduled: str | None = None
    fast2sms_template_visit_details_changed: str | None = None
    # Blank until DLT approves it; the revert notice then falls back to email.
    fast2sms_template_approval_reverted: str | None = None
    # WhatsApp: the sending number's id, Graph-style API version, template
    # language, and the approved template *names* (not ids).
    fast2sms_whatsapp_phone_number_id: str | None = None
    fast2sms_whatsapp_api_version: str = "v26.0"
    fast2sms_whatsapp_language_code: str = "en"
    fast2sms_whatsapp_template_otp: str | None = None
    fast2sms_whatsapp_template_registration_pending: str | None = None
    fast2sms_whatsapp_template_registration_confirmed: str | None = None
    fast2sms_whatsapp_template_registration_denied: str | None = None
    fast2sms_whatsapp_template_visit_rescheduled: str | None = None
    fast2sms_whatsapp_template_visit_details_changed: str | None = None
    fast2sms_whatsapp_template_approval_reverted: str | None = None

    # Public check-in-by-code abuse limits (add-sms-numeric-checkin-code): a
    # 8-digit code is guessable, so failed lookups per IP are capped.
    checkin_code_max_failures: int = 10
    checkin_code_lockout_seconds: int = 900

    # `invitations` feature config (add-pre-registration).
    invitation_max_upload_size_bytes: int = 5 * 1024 * 1024
    # Only consulted at tenant/branch provisioning and by the
    # `add-repeatable-field-groups` migration that seeded existing
    # branches — the seed value for Visitor Info's field group
    # `maxInstances`, which is the actual live enforcement point.
    # `invitations/service.py` no longer reads this setting directly.
    invitation_max_group_visitors: int = 20

    # Optional visitor/primary-contact profile photo
    # (checkin-approval-workflow-improvements) — a separate, smaller limit
    # from `invitation_max_upload_size_bytes` (ID proof scans), per
    # file-upload-handling.md §1's "tune per artifact type".
    invitation_max_photo_size_bytes: int = 2 * 1024 * 1024

    # Whole-request caps for multipart uploads (api-compliance-hardening
    # "Multipart Uploads Are Bounded in Total Size and File Count"). Sized for
    # the largest legitimate request: a 20-visitor group, each with an ID scan
    # and a photo, plus custom-field files. Per-file limits above still apply.
    max_request_body_bytes: int = Field(default=160 * 1024 * 1024, alias="MAX_REQUEST_BODY_BYTES")
    max_upload_files: int = Field(default=100, alias="MAX_UPLOAD_FILES")
    # Off: a weak JWT_SECRET_KEY in a deployed environment only warns at
    # startup, so rolling this out can't take down a server whose secret
    # hasn't been checked yet. Turn on per environment once it has.
    enforce_secret_check: bool = Field(default=False, alias="ENFORCE_SECRET_CHECK")

    # Visitor rows per `GET /invitations/export` (add-invitation-export/
    # design.md Decision 1) — an over-cap export is rejected with 422, never
    # truncated.
    invitation_export_max_rows: int = 10_000

    # User profile picture upload (add-avatar-upload-and-verify-image-storage).
    avatar_max_upload_size_bytes: int = 2 * 1024 * 1024

    # Invitation retention purge (invitations/tasks.py). `0` disables the job
    # outright — the safe default until the window is signed off. Invitations
    # whose visit date (or creation date) is older than this many days are
    # backed up, then permanently deleted, `invitation_purge_batch_size` at a
    # time, daily at `invitation_purge_hour:invitation_purge_minute` UTC.
    invitation_retention_days: int = Field(default=0, ge=0, alias="INVITATION_RETENTION_DAYS")
    invitation_purge_batch_size: int = Field(
        default=500, ge=1, le=5000, alias="INVITATION_PURGE_BATCH_SIZE"
    )
    invitation_purge_hour: int = Field(default=3, ge=0, le=23, alias="INVITATION_PURGE_HOUR")
    invitation_purge_minute: int = Field(default=0, ge=0, le=59, alias="INVITATION_PURGE_MINUTE")

    # QR check-in token encryption (add-qr-checkin-security) — a dedicated
    # key, deliberately not shared with `sso_encryption_key` even though
    # both go through `core/encryption.py`'s Fernet pattern: rotating one
    # secret for a security incident shouldn't silently invalidate the
    # other. Left unset by default, same "fails loudly when actually used"
    # posture as `sso_encryption_key`. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    qr_token_encryption_key: str | None = Field(default=None, alias="QR_TOKEN_ENCRYPTION_KEY")

    # `registrations` feature config (API-13, add-walkin-visitor-registration).
    # Fallback tenant/branch for `POST /registrations/walk-in` when the
    # caller sends no `X-Device-Key` (registrations/deps.py::get_registration_device) —
    # resolved server-side from config, same "never trust a client-supplied
    # tenant/branch id" posture as `default_tenant_slug`, never read from the
    # request itself.
    registration_default_branch_code: str = Field(
        default="MAIN", alias="REGISTRATION_DEFAULT_BRANCH_CODE"
    )

    # Per-IP slowapi limits (`core/rate_limit.py`). Only ever switched off
    # locally, for a load test whose simulated users all share one IP and
    # would otherwise measure the limiter instead of the API
    # (docs/features/qa-harness.md). Never disable it in a deployed
    # environment.
    rate_limit_enabled: bool = True

    # `identity_verification` feature config (API-15, add-identity-verification-otp).
    otp_ttl_seconds: int = 300
    otp_length: int = 6
    otp_max_attempts: int = 5
    otp_rate_limit_per_identifier: int = 5
    otp_rate_limit_window_seconds: int = 3600

    # `sso` feature config (API-19, add-sso-oidc-login). `sso_encryption_key`
    # is the Fernet key `core/encryption.py` uses to encrypt/decrypt every
    # tenant's OIDC client secret at rest — left unset by default so a
    # deployment that never configured it fails loudly the first time
    # `core/encryption.py` is actually used, rather than silently no-op'ing.
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    sso_encryption_key: str | None = Field(default=None, alias="SSO_ENCRYPTION_KEY")
    # The exact `redirect_uri` this app is registered with at every tenant's
    # IdP (e.g. `https://api.example.com/api/v1/auth/sso/callback`). Most
    # OIDC providers, including Microsoft Entra ID, require an exact,
    # pre-registered match — it can't be derived from the inbound request's
    # `Host` header, which is client-controlled and untrusted for this
    # purpose. One fixed value works for every tenant since the callback
    # route itself is tenant-agnostic (the tenant is carried in `state`,
    # not the URL) — see sso/service.py::handle_callback.
    sso_redirect_uri: str | None = Field(default=None, alias="SSO_REDIRECT_URI")
    # Where the callback redirects the browser with a short-lived exchange
    # code (design.md's "Exchange code, not tokens-in-a-redirect" decision) —
    # one global setting, not per-tenant, since only one React portal
    # deployment exists today.
    sso_frontend_callback_url: str | None = Field(default=None, alias="SSO_FRONTEND_CALLBACK_URL")
    sso_exchange_code_ttl_seconds: int = Field(default=60, alias="SSO_EXCHANGE_CODE_TTL_SECONDS")
    sso_state_ttl_seconds: int = Field(default=600, alias="SSO_STATE_TTL_SECONDS")
    # Dev-seeding-only: when all three of discovery_url/client_id/client_secret
    # are set, `scripts/seed_dev_data.py` provisions an enabled `SsoProvider`
    # row for the seeded tenant so staff SSO login can actually be clicked
    # through locally. Left unset by default — seeding stays a no-op for this
    # step exactly as it was before these settings existed. Requires a real,
    # publicly-reachable OIDC discovery endpoint: `fetch_discovery_document`'s
    # SSRF hardening rejects any private/loopback/reserved address, so a
    # placeholder or local value will not work at actual login time even
    # though it saves without error (see docs/features/sso_authentication.md).
    sso_dev_seed_discovery_url: str | None = Field(default=None, alias="SSO_DEV_SEED_DISCOVERY_URL")
    sso_dev_seed_client_id: str | None = Field(default=None, alias="SSO_DEV_SEED_CLIENT_ID")
    sso_dev_seed_client_secret: str | None = Field(default=None, alias="SSO_DEV_SEED_CLIENT_SECRET")
    sso_dev_seed_display_name: str = Field(
        default="Dev SSO Provider", alias="SSO_DEV_SEED_DISPLAY_NAME"
    )

    # Firebase Cloud Messaging — the push provider for both web and the
    # Flutter app (add-invitation-push-notifications/design.md Decision 4).
    # Points at a service-account key file (the Admin SDK's own credential
    # format); left unset by default, same "not configured" posture as
    # the Fast2SMS settings above — `notifications/fcm.py` fails loudly
    # rather than silently no-op'ing when a push is actually attempted.
    fcm_credentials_path: str | None = Field(default=None, alias="FCM_CREDENTIALS_PATH")

    @model_validator(mode="after")
    def _refuse_placeholder_secrets(self) -> Self:
        """environment-configuration "Placeholder Secrets Are Refused Outside
        Local and Testing": tokens, OTP hashes and signed URLs all derive
        from this key, so a deployment that forgot to set it must not start.
        Names the setting, never its value."""
        if self.environment.lower() in _NON_DEPLOYED_ENVIRONMENTS:
            return self
        if _is_placeholder_secret(self.jwt_secret_key):
            message = (
                "JWT_SECRET_KEY is unset, a placeholder, or shorter than "
                f"{_MIN_SECRET_LENGTH} characters in APP_ENV={self.environment!r}"
            )
            if not self.enforce_secret_check:
                warnings.warn(f"{message}; set a strong secret", RuntimeWarning, stacklevel=2)
                return self
            # Not a ValueError: pydantic would wrap that in a ValidationError
            # whose text echoes the input — including the secret.
            raise InsecureConfigurationError(f"{message}; refusing to start")
        return self


class InsecureConfigurationError(RuntimeError):
    """A deployed environment is configured with an unsafe placeholder."""


_NON_DEPLOYED_ENVIRONMENTS = frozenset({"local", "test", "testing"})
_MIN_SECRET_LENGTH = 32
_PLACEHOLDER_SECRETS = frozenset({"change-me-in-env", "changeme", "secret"})


def _is_placeholder_secret(value: str | None) -> bool:
    if not value or len(value) < _MIN_SECRET_LENGTH:
        return True
    lowered = value.lower()
    return (
        lowered in _PLACEHOLDER_SECRETS
        or "placeholder" in lowered
        or (value.startswith("__") and value.endswith("__"))
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
