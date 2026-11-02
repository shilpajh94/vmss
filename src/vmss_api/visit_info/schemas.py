import uuid

from vmss_api.core.schemas import CamelModel


class HostSearchResultOut(CamelModel):
    id: uuid.UUID
    name: str
    # Null only for an anonymous caller once PUBLIC_ENDPOINT_HARDENING is on.
    email: str | None
    department: str | None = None


class HostSearchOut(CamelModel):
    hosts: list[HostSearchResultOut]


class DepartmentLookupOut(CamelModel):
    id: uuid.UUID
    name: str


class DepartmentLookupListOut(CamelModel):
    departments: list[DepartmentLookupOut]


class VisitPurposeOut(CamelModel):
    id: uuid.UUID
    name: str


class VisitDurationOut(CamelModel):
    id: uuid.UUID
    name: str
    minutes: int


class VisitInfoOptionsOut(CamelModel):
    purposes: list[VisitPurposeOut]
    durations: list[VisitDurationOut]
