import uuid

from vmss_api.core.schemas import CamelModel


class TenantOut(CamelModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    is_active: bool
    badge_print_flow_enabled: bool = False


class TenantSettingsUpdate(CamelModel):
    """Request shape for `PATCH /tenants/me/settings` — a separate class from
    `TenantOut` (database-architecture.md §4) so a client can never set
    `id`/`slug`/`isActive` through it."""

    badge_print_flow_enabled: bool
