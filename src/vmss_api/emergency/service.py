from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.schemas import BranchScope
from vmss_api.emergency.repository import InsideRepository
from vmss_api.emergency.schemas import InsideReportOut, InsideVisitorOut, InsideZoneOut
from vmss_api.invitations.models import Invitation


def _visitor(visit: Invitation, entered_at=None) -> InsideVisitorOut:  # noqa: ANN001
    return InsideVisitorOut(
        invitation_id=visit.id,
        visitor_name=visit.primary_contact_full_name,
        host_name=visit.host_name_or_email,
        badge_number=visit.badge_number,
        entered_at=entered_at,
    )


async def inside_report(tenant_db: AsyncSession, branch_scope: BranchScope) -> InsideReportOut:
    """Two queries regardless of occupant count (design.md Decision 8)."""
    repo = InsideRepository(tenant_db)
    zones: dict = {}
    for zone, visit, entered_at in await repo.occupants_by_zone(branch_scope):
        entry = zones.setdefault(
            zone.id,
            InsideZoneOut(
                zone_id=zone.id, zone_name=zone.name, branch_id=zone.branch_id, visitors=[]
            ),
        )
        entry.visitors.append(_visitor(visit, entered_at))
    unzoned = [_visitor(v) for v in await repo.unzoned(branch_scope)]
    in_zones = {v.invitation_id for z in zones.values() for v in z.visitors}
    return InsideReportOut(
        zones=list(zones.values()),
        unzoned=unzoned,
        total_inside=len(in_zones) + len(unzoned),
    )
