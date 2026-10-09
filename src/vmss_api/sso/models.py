import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vmss_api.auth.models import Role
from vmss_api.core.database import Base, TimestampMixin


class SsoProvider(Base, TimestampMixin):
    """A tenant's single configured OIDC provider (design.md's "Two new
    tenant-scoped tables" decision — one row per tenant today, but modeled
    as a table rather than a singleton so a second concurrently-enabled
    provider is an additive row later, not a schema change).

    `client_secret_encrypted` is Fernet ciphertext (`core/encryption.py`),
    never the plaintext. `client_secret_masked` (e.g. `****1234`) is stored
    unencrypted, computed once at save time, purely so `GET /auth/sso/config`
    can render it without ever decrypting the real secret just to display it.
    """

    __tablename__ = "sso_providers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(100))
    discovery_url: Mapped[str] = mapped_column(String(500))
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret_encrypted: Mapped[str] = mapped_column(String(1000))
    client_secret_masked: Mapped[str] = mapped_column(String(20))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Off by default: an existing Admin account is otherwise rejected at the
    # SSO callback (password login only). Never lets JIT provisioning assign
    # Admin — that stays blocked in `create_role_mapping`.
    allow_admin_login: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa.false()
    )


class SsoRoleMapping(Base, TimestampMixin):
    """Maps one IdP group claim value to one Visimio role — the only
    source `sso/service.py`'s JIT provisioning ever consults to decide a new
    SSO user's role (design.md's "Role assignment only ever comes from the
    curated mapping table" decision).
    """

    __tablename__ = "sso_role_mappings"
    __table_args__ = (
        UniqueConstraint("idp_group_claim_value", name="uq_sso_role_mapping_group_claim"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idp_group_claim_value: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"))

    role: Mapped[Role] = relationship(lazy="selectin")
