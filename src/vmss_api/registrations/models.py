import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.config import settings
from vmss_api.core.database import GlobalBase

_GLOBAL = settings.global_schema_name
_TENANTS_FK = f"{_GLOBAL}.tenants.id"


class RegistrationDeviceKey(GlobalBase):
    """A provisioned credential for one branch's walk-in-registration
    kiosk/app instance (API-13). Resolved server-side from the `X-Device-Key`
    request header to a fixed `(tenant_id, branch_id)` — the same shape of
    auth-routing problem `platform.models.TenantUserIndex` solves for login
    (`database-architecture.md` §2), so it lives in the global schema too,
    reachable before any tenant-scoped session can be opened. See
    add-walkin-visitor-registration/design.md Decision 3.

    `branch_id` carries no `ForeignKey`: `branches` lives inside each
    tenant's own physical schema, not the global one, so there is no single
    `branches` table a global-schema FK could point at — same reasoning as
    `TenantUserIndex.user_id` above having no FK to a schema-per-tenant
    `users` table.
    """

    __tablename__ = "registration_device_keys"
    __table_args__ = {"schema": _GLOBAL}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(_TENANTS_FK), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    # Argon2 hash of the raw device key (`core/security.py::hash_password` —
    # same primitive, different subject). The raw key is shown to whoever
    # provisions the device exactly once and never stored.
    key_hash: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
