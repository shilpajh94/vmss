"""Sends every email template, rendered with full sample data, to the dev
mail catcher (Mailpit), so reviewers look at complete emails rather than
the minimal ones automated tests send
(serve-email-images-by-url-and-complete-contact design.md Decision 5).

The check-in QR in the confirmation and reschedule previews points at a
real signed URL when `EMAIL_ASSET_BASE_URL` is set and the tenant has an
approved invitation with an issued QR; otherwise it falls back to an
inline QR of a sample token, exactly as production would.

Usage: ddev exec uv run python scripts/send_email_previews.py [--to ADDRESS] [--tenant-slug SLUG]
"""

import argparse
import asyncio
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select

from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine, tenant_session_scope
from vmss_api.core.email_assets import sign_qr_url
from vmss_api.core.email_rendering import render_email
from vmss_api.core.emailing import InlineImage, email_sender, make_inline_image
from vmss_api.invitations.models import Invitation, InvitationQRCode
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.tenant.repository import TenantRepository

_QR_CID = "visit-qr@vmss"

TEMPLATES = (
    "visit_confirmation",
    "tracking_only",
    "denial",
    "reschedule",
    "edit",
    "submission_role",
    "host_assigned",
    "poc_assigned",
    "verification_code",
    "daily_snapshot",
)

SAMPLE_CONTEXT: dict[str, Any] = {
    "company_name": "Acme Corp",
    "logo_url": None,
    "recipient_name": "Meera Krishnan",
    "recipient_email": "meera@example.com",
    "tracking_id": "INV-B8490B0B",
    "visitor_name": "Meera Krishnan",
    "purpose": "Interview",
    "visit_date": date(2026, 10, 14),
    "visit_time": time(10, 30),
    "previous_visit_date": date(2026, 10, 12),
    "previous_visit_time": time(9, 0),
    "duration": "1 hour",
    "department": "Engineering",
    "place": "Tower A · Technopark Campus · Phase 1, Trivandrum",
    "front_desk_contact": "+91 80 4000 1000",
    "contact_title": "Your point of contact",
    "contact_name": "Priya Nair",
    "contact_detail": "+91 90000 11122",
    "is_approved": True,
    "denial_reason": "The host is unavailable on the requested date",
    "visitor_phone": "+91 98765 43210",
    "visitor_email": "meera@example.com",
    "code": "763090",
    "minutes": 5,
    "report_date": date(2026, 9, 30),
    "total_branches": 2,
    "totals": SimpleNamespace(
        buildings=3,
        floors=9,
        departments=12,
        reception_desks=3,
        security_gates=4,
        active_employees=148,
    ),
    "branches": [
        SimpleNamespace(
            branch_name="Technopark Campus",
            branch_code="TVM",
            building_count=2,
            floor_count=7,
            department_count=9,
            reception_desk_count=2,
            security_gate_count=3,
            active_employee_count=112,
        ),
        SimpleNamespace(
            branch_name="Kochi Office",
            branch_code="COK",
            building_count=1,
            floor_count=2,
            department_count=3,
            reception_desk_count=1,
            security_gate_count=1,
            active_employee_count=36,
        ),
    ],
}


async def _qr_source(tenant_slug: str) -> tuple[str, list[InlineImage], str]:
    """`(qr_src, inline_images, description)` for the preview QR."""
    async with AsyncSessionLocal() as db:
        tenant = await TenantRepository(db).get_by_slug(tenant_slug)
    if tenant is not None and settings.email_asset_base_url:
        async with tenant_session_scope(tenant.schema_name) as session:
            row = (
                await session.execute(
                    select(Invitation, InvitationQRCode)
                    .join(InvitationQRCode, InvitationQRCode.invitation_id == Invitation.id)
                    .where(Invitation.deleted_at.is_(None))
                    .order_by(Invitation.created_at.desc())
                    .limit(1)
                )
            ).first()
        if row is not None:
            invitation, _ = row
            # A preview must stay fetchable even for a long-past dev visit.
            expires_at = max(invitation.expires_at, datetime.now(UTC) + timedelta(days=1))
            url = sign_qr_url(tenant.id, invitation.id, expires_at)
            if url is not None:
                return url, [], f"signed URL for invitation {invitation.tracking_id}"
    png = await generate_qr_png("preview-sample-token")
    return (
        f"cid:{_QR_CID}",
        [make_inline_image(png, "image/png", _QR_CID)],
        "inline fallback (no EMAIL_ASSET_BASE_URL or no issued QR in this tenant)",
    )


async def send_previews(to: str, tenant_slug: str) -> None:
    try:
        qr_src, qr_images, qr_description = await _qr_source(tenant_slug)
        print(f"QR: {qr_description}")
        for name in TEMPLATES:
            has_qr = name in {"visit_confirmation", "reschedule"}
            rendered = render_email(name, {**SAMPLE_CONTEXT, "qr_src": qr_src if has_qr else None})
            await email_sender.send(
                to=to,
                subject=f"[Preview] {rendered.subject}",
                body=rendered.text,
                html_body=rendered.html,
                inline_images=qr_images if has_qr else (),
            )
            print(f"sent {name}: {rendered.subject}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--to", default="preview@visimio.local")
    parser.add_argument("--tenant-slug", default=settings.default_tenant_slug)
    args = parser.parse_args()
    asyncio.run(send_previews(args.to, args.tenant_slug))


if __name__ == "__main__":
    main()
