"""Single import surface for the dependencies almost every feature's
`router.py` needs. A route typically wants some subset of `get_db` (global
schema), `get_tenant`/`get_tenant_db` (resolved tenant + its schema-bound
session), `get_current_user`, and `require_permission` — importing all of
them from one place beats reaching into `core.database`/`core.tenancy`
separately every time.
"""

from typing import Annotated

from fastapi import Query

from vmss_api.core.database import get_db
from vmss_api.core.tenancy import get_current_user, get_tenant, get_tenant_db, require_permission

__all__ = [
    "get_current_user",
    "get_db",
    "get_pagination",
    "get_tenant",
    "get_tenant_db",
    "require_permission",
]


async def get_pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="pageSize")] = 20,
) -> tuple[int, int]:
    """Shared `page`/`pageSize` query params for list endpoints
    (api-conventions.md §1) — one dependency instead of every feature's
    `router.py` redeclaring the same two `Query()` params.
    """
    return page, page_size
