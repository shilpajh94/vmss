import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.storage import FileTooLargeError, UnsupportedFileTypeError, validate_upload
from vmss_api.core.storage import save as storage_save
from vmss_api.invitations import tasks
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.schemas import InvitationCreate, RegistrationSource
from vmss_api.tenant.models import Tenant


async def _generate_unique_tracking_id(repo: InvitationRepository) -> str:
    """`INV-XXXXXXXX` — 32 bits of randomness is more than enough given this
    only needs to be unique per tenant schema, but the retry loop (rather
    than trusting a single draw) is what actually guarantees it against the
    unique constraint, not the odds.
    """
    for _ in range(5):
        candidate = "INV-" + secrets.token_hex(4).upper()
        if await repo.get_by_tracking_id(candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique invitation tracking id")


def _current_request_id() -> str:
    return structlog.contextvars.get_contextvars().get("request_id", "")


def _validate_id_proof(content: bytes, max_size: int) -> str:
    """Returns the sniffed content type. No storage I/O — call this for
    every visitor's file before persisting any of them, so a submission
    rejected because one visitor's file is invalid never leaves an earlier
    visitor's file written to storage.
    """
    try:
        return validate_upload(content, max_size_bytes=max_size)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


async def create_invitation(
    tenant_db: AsyncSession,
    payload: InvitationCreate,
    *,
    branch_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    tenant: Tenant,
    primary_contact_id_proof_content: bytes,
    visitor_id_proof_contents: list[bytes],
    source: RegistrationSource = RegistrationSource.staff_pre_registration,
) -> Invitation:
    """API-09 (and, via `source=visitor_walk_in`, API-13). Creates a fully
    populated, immediately-`submitted` invitation in a single call — the
    validation, ID-proof storage, and child-row construction that used to
    happen in a separate self-registration step (API-10, now removed) happen
    here instead (design.md Decisions 1 and 2). Generates the human-readable
    expiry-bound tracking ID and enqueues the visit-confirmation dispatch
    (API-11) — never sent inline (`background-jobs.md` §5).

    `created_by_user_id` is `None` for a walk-in registration — there is no
    authenticated staff creator to record
    (add-walkin-visitor-registration/design.md Decision 1).
    """
    if len(payload.visitors) > settings.invitation_max_group_visitors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A group registration may not list more than "
            f"{settings.invitation_max_group_visitors} visitors",
        )
    if len(payload.visitors) != len(visitor_id_proof_contents):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Visitor list and uploaded ID proof files must match in count",
        )

    repo = InvitationRepository(tenant_db)
    tracking_id = await _generate_unique_tracking_id(repo)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.invitation_token_ttl_hours)
    max_size = settings.invitation_max_upload_size_bytes

    # Validate every file before persisting any of them (spec.md "Each Visitor
    # Has at Least One Reachable Contact and an ID Proof") — otherwise a later
    # visitor's invalid file would abort the request after an earlier
    # visitor's file was already written to storage.
    primary_content_type = _validate_id_proof(primary_contact_id_proof_content, max_size)
    visitor_content_types = [
        _validate_id_proof(content, max_size) for content in visitor_id_proof_contents
    ]

    primary_key = await storage_save(
        tenant.id, "invitations/id-proof", primary_contact_id_proof_content, primary_content_type
    )

    invitation = Invitation(
        id=uuid.uuid4(),
        branch_id=branch_id,
        created_by_user_id=created_by_user_id,
        source=source.value,
        registration_type=payload.registration_type.value,
        status="submitted",
        tracking_id=tracking_id,
        expires_at=expires_at,
        submitted_at=now,
        primary_contact_full_name=payload.primary_contact.full_name,
        primary_contact_email=payload.primary_contact.email,
        primary_contact_phone=payload.primary_contact.phone,
        primary_contact_preferred_contact_method=(
            payload.primary_contact.preferred_contact_method.value
        ),
        primary_contact_id_proof_type=payload.primary_contact.id_proof_type.value,
        primary_contact_id_proof_storage_key=primary_key,
        purpose_of_visit=payload.visit_details.purpose_of_visit,
        host_name_or_email=payload.visit_details.host_name_or_email,
        preferred_visit_date=payload.visit_details.preferred_visit_date,
        preferred_visit_time=payload.visit_details.preferred_visit_time,
        expected_duration=payload.visit_details.expected_duration,
        department_to_visit=payload.visit_details.department_to_visit,
        additional_notes=payload.visit_details.additional_notes,
        carried_items=[item.value for item in payload.carried_items.items],
        carried_items_description=payload.carried_items.item_description,
        terms_accepted=payload.consents.terms_accepted,
        data_processing_accepted=payload.consents.data_processing_accepted,
        safety_guidelines_accepted=payload.consents.safety_guidelines_accepted,
        consent_recorded_at=now,
    )
    tenant_db.add(invitation)

    visitor_rows = [
        InvitationVisitor(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            full_name=visitor.full_name,
            email=visitor.email,
            phone=visitor.phone,
            id_proof_type=visitor.id_proof_type.value,
            id_proof_storage_key=await storage_save(
                tenant.id, "invitations/id-proof", content, content_type
            ),
        )
        for visitor, content, content_type in zip(
            payload.visitors, visitor_id_proof_contents, visitor_content_types, strict=True
        )
    ]
    vehicle_rows = [
        InvitationVehicle(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            vehicle_type=vehicle.vehicle_type.value,
            license_plate=vehicle.license_plate,
            make_model=vehicle.make_model,
            color=vehicle.color,
        )
        for vehicle in payload.vehicles
    ]
    repo.add_visitors(visitor_rows)
    repo.add_vehicles(vehicle_rows)

    await tenant_db.commit()

    created = await repo.get_with_children(invitation.id)
    assert created is not None  # just committed; guaranteed to exist

    tasks.send_visit_confirmation.delay(
        request_id=_current_request_id(),
        tenant_schema=tenant.schema_name,
        invitation_id=str(invitation.id),
    )
    return created


async def track_by_tracking_id(tenant_db: AsyncSession, tracking_id: str) -> Invitation:
    invitation = await InvitationRepository(tenant_db).get_by_tracking_id(tracking_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def track_by_email(tenant_db: AsyncSession, email: str) -> list[Invitation]:
    """Deliberately returns bare `Invitation` rows with no eager-loaded
    children — the router maps these onto `InvitationTrackingSummaryOut`
    (tracking id + status only), never the full-detail schema, per spec.md's
    minimal-disclosure requirement.
    """
    return await InvitationRepository(tenant_db).list_by_primary_contact_email(email)
