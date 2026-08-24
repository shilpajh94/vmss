from fastapi import APIRouter

from vmss_api.auth.router import router as auth_router
from vmss_api.identity_verification.router import router as identity_verification_router
from vmss_api.invitations.router import router as invitations_router
from vmss_api.org_structure.router import router as org_structure_router
from vmss_api.platform.router import router as platform_router
from vmss_api.registrations.router import router as registrations_router
from vmss_api.reports.router import router as reports_router
from vmss_api.tenant.router import router as tenant_router
from vmss_api.visit_info.router import router as visit_info_router
from vmss_api.visitors.router import router as visitors_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(tenant_router)
api_router.include_router(org_structure_router)
api_router.include_router(platform_router)
api_router.include_router(visitors_router)
api_router.include_router(invitations_router)
api_router.include_router(registrations_router)
api_router.include_router(reports_router)
api_router.include_router(identity_verification_router)
api_router.include_router(visit_info_router)
