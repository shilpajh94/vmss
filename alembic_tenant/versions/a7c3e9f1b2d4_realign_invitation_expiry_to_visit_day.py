"""realign open invitations' expiry to the end of their visit day

Revision ID: a7c3e9f1b2d4
Revises: e5f7a9b1c3d4
Create Date: 2026-10-12 00:00:00.000000

Invitations created before the end-of-visit-day rule still carry the old
fixed creation TTL (`created_at + 168h`), which can expire a pass before
the visit even happens. This recomputes `expires_at` as 23:59:59 on
`preferred_visit_date` in the visit timezone (`companies.default_timezone`
→ `tenants.timezone` → UTC, same precedence as
`invitations/service.py::_visit_timezone`, copied rather than imported so
the migration stays fixed even if the app logic moves on).

Only non-terminal rows whose `expires_at` still matches that old TTL
(±5 s) are touched, so staff extensions and rows already realigned by
approve/reschedule are left alone. Data only, no DDL. Downgrade is a
no-op — the previous values were wrong, not worth restoring.
"""

from collections.abc import Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b2d4"
down_revision: str | Sequence[str] | None = "e5f7a9b1c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_TTL_SECONDS = 168 * 3600
_TOLERANCE_SECONDS = 5


def _valid_zone(name: str | None) -> str | None:
    if not name:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    return name


def upgrade() -> None:
    schema = op.get_context().version_table_schema
    conn = op.get_bind()
    company_tz = conn.execute(
        text(f'SELECT default_timezone FROM "{schema}".companies WHERE deleted_at IS NULL LIMIT 1')
    ).scalar_one_or_none()
    tenant_tz = conn.execute(
        text(f"SELECT timezone FROM {settings.global_schema_name}.tenants WHERE schema_name = :s"),
        {"s": schema},
    ).scalar_one_or_none()
    zone = _valid_zone(company_tz) or _valid_zone(tenant_tz) or "UTC"

    conn.execute(
        text(
            f'UPDATE "{schema}".invitations '
            "SET expires_at = (preferred_visit_date + time '23:59:59') AT TIME ZONE :zone "
            "WHERE preferred_visit_date IS NOT NULL "
            "AND status IN ('pending', 'submitted', 'approved', 'checked_in') "
            "AND abs(extract(epoch FROM (expires_at - created_at)) - :ttl) < :tolerance"
        ),
        {"zone": zone, "ttl": _OLD_TTL_SECONDS, "tolerance": _TOLERANCE_SECONDS},
    )


def downgrade() -> None:
    pass
