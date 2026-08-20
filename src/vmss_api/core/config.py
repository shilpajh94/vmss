from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VMSS API"
    environment: str = "local"
    debug: bool = True
    log_level: str = "INFO"

    # Split rather than a single DATABASE_URL so a password containing a
    # reserved URL character (`@`, `:`, `/`, `%`) can't corrupt the parsed
    # host/port the way it would if pasted unescaped into one connection
    # string. `URL.create` below percent-encodes each part itself.
    db_user: str = "vms_user"
    db_password: str = "YtHtwq@196"
    db_host: str = "10.10.100.237"
    db_port: int = 32735
    db_name: str = "vms_db"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    jwt_secret_key: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    default_tenant_slug: str = "default"

    # The Postgres schema holding cross-tenant registry tables (tenants,
    # superadmins, the auth index, ...). Every tenant gets its own
    # `{tenant_schema_prefix}{slug}` schema — see database-architecture.md §2.
    global_schema_name: str = "global"
    tenant_schema_prefix: str = "tenant_"

    # `core/storage.py` — local-disk-backed in dev, per database-architecture.md
    # §1; swapping to S3-compatible object storage in prod is a config change
    # behind the same interface, not a call-site change.
    storage_root: str = "./var/storage"

    # SMTP settings for `invitations/notifications.py`'s `SmtpEmailSender` —
    # see add-pre-registration/design.md Decision 4. Defaults point at a local
    # dev mail-catcher (e.g. mailhog/mailpit) so a fresh checkout doesn't need
    # a real mail server to send/queue without erroring.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False
    smtp_from_address: str = "no-reply@vmss.local"

    # SMS gateway — no vendor chosen yet (design.md Open Questions); these are
    # placeholders the `SmsSender` adapter reads once one is picked. Left
    # unset by default, which the adapter treats as "not configured" and
    # fails visibly per background-jobs.md §4, rather than pretending to send.
    sms_gateway_base_url: str | None = None
    sms_gateway_api_key: str | None = None
    sms_from_number: str | None = None

    # `invitations` feature config (add-pre-registration).
    invitation_token_ttl_hours: int = 168
    invitation_max_upload_size_bytes: int = 5 * 1024 * 1024
    invitation_max_group_visitors: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
