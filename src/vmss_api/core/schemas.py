import math
import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

type BranchScope = Literal["all"] | frozenset[uuid.UUID]
"""Which branches a caller's request is scoped to, once `X-Branch-ID` is
optional (api-conventions.md-adjacent RBAC concern, not a request schema) —
`"all"` for a company-wide grant, otherwise the specific branch ids the
caller holds a given permission at (a single-id request still yields a
one-element `frozenset`). See `org_structure/deps.py::require_branch_scope`
and `auth/models.py::User.authorized_branch_ids`.
"""


class SortOrder(StrEnum):
    """`asc`/`desc` for a list endpoint's `sort_order` param
    (api-conventions.md §1) — shared across every feature's query schema so
    they don't each redeclare the same two-value enum.
    """

    asc = "asc"
    desc = "desc"


class CamelModel(BaseModel):
    """Base for every request/response schema.

    Python fields stay snake_case; the JSON boundary is camelCase for the
    React/Flutter clients. See fastapi-architecture.md §3.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Envelope[T](CamelModel):
    """Documents the `{success, message, data}` shape `success_response`
    actually returns, so a route's `response_model` matches its real body.

    `success_response()` (`core/responses.py`) builds the `JSONResponse`
    itself rather than returning a model FastAPI serializes — so this is
    documentation only and does not change runtime behavior. Every route
    using `success_response` should set
    `response_model=Envelope[<YourResponseSchema>]` so Swagger shows the
    real response shape instead of an untyped body.
    """

    success: bool = True
    message: str = "Success"
    data: T


class PaginationMeta(CamelModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(cls, *, page: int, page_size: int, total: int) -> "PaginationMeta":
        """The same `totalPages` arithmetic `paginated_response` uses."""
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        )


class PaginatedEnvelope[T](CamelModel):
    """Documents `paginated_response`'s `{success, message, data, pagination}`
    shape (`core/responses.py`) — the list-endpoint counterpart to `Envelope`,
    per api-conventions.md §1.
    """

    success: bool = True
    message: str = "Success"
    data: list[T]
    pagination: PaginationMeta
