from fastapi import APIRouter

from vmss_api.approvals.router import router as approvals_router
from vmss_api.audit_trail.router import router as audit_trail_router
from vmss_api.auth.router import router as auth_router
from vmss_api.checkin.kiosk_router import router as kiosk_checkin_router
from vmss_api.checkin.router import router as checkin_router
from vmss_api.core.email_assets_router import router as email_assets_router
from vmss_api.core.storage_router import router as storage_router
from vmss_api.dashboard.router import router as dashboard_router
from vmss_api.devices.router import router as devices_router
from vmss_api.devices.router import settings_router as device_settings_router
from vmss_api.form_builder.router import router as form_builder_router
from vmss_api.identity_verification.router import router as identity_verification_router
from vmss_api.invitations.email_assets_router import router as invitation_email_assets_router
from vmss_api.invitations.router import router as invitations_router
from vmss_api.invitations.router import router_v2 as invitations_router_v2
from vmss_api.kiosks.router import router as kiosks_router
from vmss_api.notifications.router import router as notifications_router
from vmss_api.org_structure.router import router as org_structure_router
from vmss_api.platform.router import router as platform_router
from vmss_api.registrations.router import router as registrations_router
from vmss_api.reports.router import router as reports_router
from vmss_api.sso.router import router as sso_router
from vmss_api.tenant.router import router as tenant_router
from vmss_api.timeline.router import router as timeline_router
from vmss_api.visit_info.router import router as visit_info_router
from vmss_api.visitor_return_visit.router import router as visitor_return_visit_router
from vmss_api.visitors.router import router as visitors_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(audit_trail_router)
api_router.include_router(tenant_router)
api_router.include_router(org_structure_router)
api_router.include_router(kiosks_router)
api_router.include_router(devices_router)
api_router.include_router(device_settings_router)
api_router.include_router(platform_router)
api_router.include_router(visitors_router)
api_router.include_router(timeline_router)
api_router.include_router(form_builder_router)
api_router.include_router(invitations_router)
api_router.include_router(approvals_router)
api_router.include_router(registrations_router)
api_router.include_router(reports_router)
api_router.include_router(identity_verification_router)
api_router.include_router(sso_router)
api_router.include_router(visit_info_router)
api_router.include_router(notifications_router)
api_router.include_router(dashboard_router)
api_router.include_router(storage_router)
api_router.include_router(email_assets_router)
api_router.include_router(invitation_email_assets_router)
api_router.include_router(visitor_return_visit_router)
api_router.include_router(checkin_router)
api_router.include_router(kiosk_checkin_router)

# --- add-public-checkin-endpoint: minimal /api/v2 mount ----------------------
# Scoped to this one endpoint, not a wholesale re-exposure of every v1 route
# under v2 (design.md Goals/Non-Goals). Future breaking changes to other
# resources make their own versioning decision rather than defaulting here.
api_router_v2 = APIRouter()
api_router_v2.include_router(invitations_router_v2)
