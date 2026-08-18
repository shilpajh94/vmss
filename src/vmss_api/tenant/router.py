from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from vmss_api.core.deps import get_tenant, require_permission
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.schemas import TenantOut

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get(
    "/me",
    response_model=Envelope[TenantOut],
    dependencies=[Depends(require_permission("tenants:read"))],
)
async def get_my_tenant(tenant: Annotated[Tenant, Depends(get_tenant)]) -> JSONResponse:
    return success_response(data=TenantOut.model_validate(tenant))
