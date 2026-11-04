import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.config import settings
from vmss_api.core.database import GlobalBase, TimestampMixin


class Tenant(GlobalBase, TimestampMixin):
    """The tenant registry row — lives in the global schema, one row per
    tenant. `schema_name` is the Postgres schema holding that tenant's own
    domain tables (`users`, `roles`, future `visitors`/`invitations`/...).

    See database-architecture.md §2. Exactly one row exists today
    (single-tenant rollout), but nothing assumes there's only one — see
    `core/tenancy.py::get_tenant`.
    """

    __tablename__ = "tenants"
    __table_args__ = {"schema": settings.global_schema_name}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    schema_name: Mapped[str] = mapped_column(String(63), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Sole gate for the badge print flow (add-badge-print-flow).
    badge_print_flow_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa.false()
    )
    # Sole gate for zone access control (add-zone-access-control).
    zone_access_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa.false()
    )
