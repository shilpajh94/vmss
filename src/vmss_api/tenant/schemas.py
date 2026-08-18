import uuid

from vmss_api.core.schemas import CamelModel


class TenantOut(CamelModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    is_active: bool
