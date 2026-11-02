import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.logging import current_request_id, logger
from vmss_api.core.redis import get_redis
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.core.timezones import display_name as display_tz_name
from vmss_api.core.timezones import sql_name as sql_tz_name
from vmss_api.form_builder import service as form_builder_service
from vmss_api.form_builder import validation as form_builder_validation
from vmss_api.invitations import tasks
from vmss_api.invitations.approval import (
    approve_invitation as approve_invitation,
)
from vmss_api.invitations.approval import (
    current_approval_steps as current_approval_steps,
)
from vmss_api.invitations.approval import (
    deny_invitation as deny_invitation,
)
from vmss_api.invitations.approval import (
    get_current_approval_step as get_current_approval_step,
)
from vmss_api.invitations.approval import (
    revert_invitation_approval as revert_invitation_approval,
)
from vmss_api.invitations.checkin import (
    _ARCHIVED_CHECK_IN_DETAIL as _ARCHIVED_CHECK_IN_DETAIL,
)
from vmss_api.invitations.checkin import (
    _check_in_resolved as _check_in_resolved,
)
from vmss_api.invitations.checkin import (
    _check_out_resolved as _check_out_resolved,
)
from vmss_api.invitations.checkin import (
    _enforce_device_location as _enforce_device_location,
)
from vmss_api.invitations.checkin import (
    _get_invitation_by_checkin_code_or_400 as _get_invitation_by_checkin_code_or_400,
)
from vmss_api.invitations.checkin import (
    _get_invitation_by_qr_token_or_400 as _get_invitation_by_qr_token_or_400,
)
from vmss_api.invitations.checkin import (
    _perform_check_in as _perform_check_in,
)
from vmss_api.invitations.checkin import (
    branch_of_tracking_id as branch_of_tracking_id,
)
from vmss_api.invitations.checkin import (
    check_in_by_code as check_in_by_code,
)
from vmss_api.invitations.checkin import (
    check_in_by_qr_token as check_in_by_qr_token,
)
from vmss_api.invitations.checkin import (
    check_in_invitation_by_tracking_id as check_in_invitation_by_tracking_id,
)
from vmss_api.invitations.checkin import (
    check_out_by_code as check_out_by_code,
)
from vmss_api.invitations.checkin import (
    check_out_by_qr_token as check_out_by_qr_token,
)
from vmss_api.invitations.checkin import (
    check_out_invitation as check_out_invitation,
)
from vmss_api.invitations.checkin import (
    issue_badge as issue_badge,
)
from vmss_api.invitations.checkin import (
    override_watchlist as override_watchlist,
)
from vmss_api.invitations.checkin import (
    reprint_badge as reprint_badge,
)
from vmss_api.invitations.common import (
    _ACTIVE_STATUSES as _ACTIVE_STATUSES,
)
from vmss_api.invitations.common import (
    _CHECKIN_CODE_LENGTH as _CHECKIN_CODE_LENGTH,
)
from vmss_api.invitations.common import (
    _STAFF_EVENT_PUSH_BUILDERS as _STAFF_EVENT_PUSH_BUILDERS,
)
from vmss_api.invitations.common import (
    ListDrillDown as ListDrillDown,
)
from vmss_api.invitations.common import (
    _drill_down_filters,
)
from vmss_api.invitations.common import (
    _end_of_visit_day_utc as _end_of_visit_day_utc,
)
from vmss_api.invitations.common import (
    _generate_unique_badge_number as _generate_unique_badge_number,
)
from vmss_api.invitations.common import (
    _generate_unique_checkin_code as _generate_unique_checkin_code,
)
from vmss_api.invitations.common import (
    _issue_checkin_code as _issue_checkin_code,
)
from vmss_api.invitations.common import (
    _issue_qr_code as _issue_qr_code,
)
from vmss_api.invitations.common import (
    _match_department_by_name as _match_department_by_name,
)
from vmss_api.invitations.common import (
    _notify_activated_approver as _notify_activated_approver,
)
from vmss_api.invitations.common import (
    _notify_host as _notify_host,
)
from vmss_api.invitations.common import (
    _notify_responsible_staff as _notify_responsible_staff,
)
from vmss_api.invitations.common import (
    _push_point_of_contact as _push_point_of_contact,
)
from vmss_api.invitations.common import (
    _resolve_building as _resolve_building,
)
from vmss_api.invitations.common import (
    _restart_approval as _restart_approval,
)
from vmss_api.invitations.common import (
    _staff_email_recipients as _staff_email_recipients,
)
from vmss_api.invitations.common import (
    _unique_code as _unique_code,
)
from vmss_api.invitations.common import (
    _visit_timezone as _visit_timezone,
)
from vmss_api.invitations.common import (
    resolve_visit_timezone as resolve_visit_timezone,
)
from vmss_api.invitations.creation import (
    _build_approval_steps as _build_approval_steps,
)
from vmss_api.invitations.creation import (
    _generate_unique_tracking_id as _generate_unique_tracking_id,
)
from vmss_api.invitations.creation import (
    _group_field_file_id as _group_field_file_id,
)
from vmss_api.invitations.creation import (
    _resolve_active_branch as _resolve_active_branch,
)
from vmss_api.invitations.creation import (
    _resolve_active_category as _resolve_active_category,
)
from vmss_api.invitations.creation import (
    _resolve_visit_detail_ids as _resolve_visit_detail_ids,
)
from vmss_api.invitations.creation import (
    _validate_id_proof as _validate_id_proof,
)
from vmss_api.invitations.creation import (
    _validate_photo as _validate_photo,
)
from vmss_api.invitations.creation import (
    create_invitation as create_invitation,
)
from vmss_api.invitations.edit import (
    _LOCATION_EDIT_FIELDS as _LOCATION_EDIT_FIELDS,
)
from vmss_api.invitations.edit import (
    _RESCHEDULABLE_STATUSES as _RESCHEDULABLE_STATUSES,
)
from vmss_api.invitations.edit import (
    _poc_eligible as _poc_eligible,
)
from vmss_api.invitations.edit import (
    _reject_past_visit_date as _reject_past_visit_date,
)
from vmss_api.invitations.edit import (
    _reschedule_archived as _reschedule_archived,
)
from vmss_api.invitations.edit import (
    _resolve_edit_changes as _resolve_edit_changes,
)
from vmss_api.invitations.edit import (
    edit_invitation as edit_invitation,
)
from vmss_api.invitations.edit import (
    extend_invitation as extend_invitation,
)
from vmss_api.invitations.edit import (
    reschedule_invitation as reschedule_invitation,
)
from vmss_api.invitations.export import (
    _EXPORT_MEDIA_TYPES as _EXPORT_MEDIA_TYPES,
)
from vmss_api.invitations.export import (
    ExportTooLargeError as ExportTooLargeError,
)
from vmss_api.invitations.export import (
    InvitationExportFile as InvitationExportFile,
)
from vmss_api.invitations.export import (
    export_invitations as export_invitations,
)
from vmss_api.invitations.models import (
    Invitation,
)
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.repository import (
    CalendarCriteria,
    InvitationRepository,
)
from vmss_api.invitations.repository import phone_digits as phone_digits
from vmss_api.invitations.schemas import (
    CALENDAR_DEFAULT_STATUSES,
    CalendarDateRange,
    CalendarDayOut,
    CalendarEventOut,
    CalendarFeedOut,
    CalendarScope,
    ClearInvitationsOut,
    ClearInvitationsRequest,
    InvitationLookupPrefillOut,
    InvitationSortableField,
    InvitationStatus,
)
from vmss_api.org_structure.deps import resolve_branch_scope
from vmss_api.org_structure.models import Branch, Building, Department
from vmss_api.org_structure.service import get_default_host_role
from vmss_api.tenant.models import Tenant


async def get_invitation(tenant_db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
    """Plain by-id fetch, no eager-loaded children — used by
    `POST /invitations/{id}/approve` to resolve the invitation's own
    `branch_id` for `authorize_branch_id_tolerant` before the state
    transition.
    """
    invitation = await InvitationRepository(tenant_db).get(invitation_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def get_invitation_detail(tenant_db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
    """Eager-loaded counterpart of `get_invitation` — backs
    `GET /invitations/{id}`, whose response schema (`InvitationDetailOut`)
    serializes `visitors`/`vehicles` the same way `InvitationTrackingOut`
    does.
    """
    invitation = await InvitationRepository(tenant_db).get_with_children(invitation_id)
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def get_invitation_location(
    tenant_db: AsyncSession, invitation: Invitation
) -> tuple[Branch, Department | None, Building | None]:
    """Resolves `invitation`'s branch and, when it has a `department_id` on
    file, that department's building — backs the `branch`/`building`/
    `department` fields on `InvitationDetailOut` and `InvitationQrCheckInOut`
    (enrich-invitation-checkin-and-detail-views/design.md Decision 5).
    """
    return await InvitationRepository(tenant_db).get_location(
        branch_id=invitation.branch_id,
        department_id=invitation.department_id,
        building_id=invitation.building_id,
    )


@dataclass(frozen=True)
class InvitationDetailFormContext:
    """Per-branch form-builder lookups `invitations/router.py`'s detail-view
    serializers need to render `GET /invitations/{id}` (add-generic-custom-
    field-file-url-resolution): `visitor_info_groups` (keyed by group id —
    backs `_group_collected_visitor_detail_outs`'s visitor synthesis), plus
    which `file_upload`-typed field ids appear in each of `customFields`/
    `primaryContactCustomFields`/a vehicle's `customFields`/a `groups`
    instance (restructure-walkin-payload-by-field-id — referenced by id,
    never by key), so those readers know which raw storage keys need
    resolving to a signed URL rather than being serialized straight from
    the ORM (see the note on `service.py::create_invitation`'s
    `customFieldValues`/`primaryContactCustomFieldValues`/`groupFieldValues`
    storage — "no reader resolves it to a signed URL yet").
    """

    visitor_info_groups: dict[str, dict[str, Any]]
    invitation_scope_file_ids: set[str]
    visitor_info_file_ids: set[str]
    vehicle_info_file_ids: set[str]
    group_file_ids: dict[str, set[str]]
    field_meta: dict[str, dict[str, str]] = dc_field(default_factory=dict)
    group_names: dict[str, str] = dc_field(default_factory=dict)


async def get_invitation_detail_form_context(
    tenant_db: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> InvitationDetailFormContext:
    """Resolves `branch_id`'s effective form once and derives every
    form-shape lookup the detail view's serializers need, rather than each
    one separately re-resolving it (still a Redis round-trip per call even
    though `resolve_effective_form` itself is cache-backed)."""
    redis = await get_redis()
    effective_form = await form_builder_service.resolve_effective_form(
        tenant_db, redis, tenant_id=tenant.id, branch_id=branch_id
    )
    visitor_info_file_ids = {
        field["id"]
        for field in form_builder_validation.custom_fields_for_step(effective_form, "visitor_info")
        if field["fieldType"] == "file_upload"
    }
    vehicle_info_file_ids = {
        field["id"]
        for field in form_builder_validation.custom_fields_for_step(effective_form, "vehicle_info")
        if field["fieldType"] == "file_upload"
    }
    invitation_scope_file_ids = {
        field["id"]
        for field in form_builder_validation.custom_fields_for_invitation_scope(effective_form)
        if field["fieldType"] == "file_upload"
    }
    group_file_ids = {
        group["id"]: {
            field["id"] for field in group["fields"] if field["fieldType"] == "file_upload"
        }
        for group in form_builder_validation.custom_groups_for_invitation_scope(effective_form)
    }
    return InvitationDetailFormContext(
        visitor_info_groups=form_builder_validation.custom_groups_for_step(
            effective_form, "visitor_info"
        ),
        invitation_scope_file_ids=invitation_scope_file_ids,
        visitor_info_file_ids=visitor_info_file_ids,
        vehicle_info_file_ids=vehicle_info_file_ids,
        group_file_ids=group_file_ids,
        field_meta={
            f["id"]: {"key": f["key"], "label": f["label"]}
            for step in effective_form
            for f in step["fields"]
        },
        group_names={g["id"]: g["name"] for step in effective_form for g in step.get("groups", [])},
    )


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


def status_changed_at(invitation: Invitation) -> datetime:
    """Python mirror of `repository._status_changed_at_expr`, so the list
    row's `statusChangedAt` is exactly the value `sortBy=status_changed_at`
    ordered by (sort-invitation-board-by-status-date/design.md Decision 2).
    Keep the two in step — `test_status_changed_at_matches_sql_ordering`
    checks it.
    """
    by_status: datetime | None
    if invitation.status == "submitted":
        candidates = [invitation.submitted_at, invitation.approval_reverted_at]
        if invitation.archived_at is not None:
            candidates.append(invitation.rescheduled_at)
        present = [value for value in candidates if value is not None]
        by_status = max(present) if present else None
    else:
        by_status = {
            "approved": invitation.approved_at,
            "checked_in": invitation.checked_in_at,
            "checked_out": invitation.checked_out_at,
            "denied": invitation.denied_at,
            "archived": invitation.archived_at,
        }.get(invitation.status)
    return by_status or invitation.submitted_at or invitation.created_at


async def list_invitations_page(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope | None,
    relevant_to_user_id: uuid.UUID | None = None,
    default_host_role_id: uuid.UUID | None = None,
    status: str | None,
    registration_type: str | None,
    source: str | None,
    search: str | None,
    page: int,
    page_size: int,
    sort_by: InvitationSortableField,
    sort_order: SortOrder,
    purpose_of_visit: str | None = None,
    tenant_id: uuid.UUID | None = None,
    drill_down: ListDrillDown | None = None,
) -> tuple[list[Invitation], int]:
    extra: dict[str, Any] = {}
    if drill_down is not None:
        assert tenant_id is not None
        extra = await _drill_down_filters(tenant_db, tenant_id, drill_down)
    return await InvitationRepository(tenant_db).list_page(
        branch_scope=branch_scope,
        relevant_to_user_id=relevant_to_user_id,
        default_host_role_id=default_host_role_id,
        status=status,
        registration_type=registration_type,
        source=source,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        purpose_of_visit=purpose_of_visit,
        **extra,
    )


# --- add-staff-calendar ------------------------------------------------------

CALENDAR_EVENT_LIMIT = 1000
"""design.md D4 — `days` totals stay exact above it; only `events` is cut."""


async def _calendar_criteria(
    tenant_db: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    date_from: date,
    date_to: date,
    scope: CalendarScope,
    statuses: list[InvitationStatus] | None,
    x_branch_id: uuid.UUID | None,
) -> tuple[CalendarCriteria, Literal["mine", "branch"], tzinfo]:
    """Who sees what, for every calendar endpoint — one builder, so the feed
    and the paged day can't drift (improve-calendar-scale-and-theme-switch
    design.md A1). `auto` resolves to `branch` for anyone holding
    `invitations:view-all` anywhere, else `mine` — decided here rather than
    by the client, which can't see permissions (add-staff-calendar D2).
    `branch` goes through the same `resolve_branch_scope` the list uses, so
    its 403/404s are identical.
    """
    permission = "invitations:view-all"
    if scope is CalendarScope.auto:
        has_branch_view = bool(user.authorized_branch_ids(permission))
        scope = CalendarScope.branch if has_branch_view else CalendarScope.mine

    branch_scope: BranchScope | None = None
    default_host_role_id: uuid.UUID | None = None
    if scope is CalendarScope.branch:
        branch_scope = await resolve_branch_scope(tenant_db, user, permission, x_branch_id)
    else:
        default_host_role_id = (await get_default_host_role(tenant_db)).id

    tz = await resolve_visit_timezone(tenant_db, tenant)
    criteria = CalendarCriteria(
        branch_scope=branch_scope,
        relevant_to_user_id=user.id if scope is CalendarScope.mine else None,
        default_host_role_id=default_host_role_id,
        date_from=date_from,
        date_to=date_to,
        starts_at=datetime.combine(date_from, time.min, tzinfo=tz).astimezone(UTC),
        ends_before=datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz).astimezone(
            UTC
        ),
        timezone=sql_tz_name(tz),
        statuses=tuple(s.value for s in (statuses or CALENDAR_DEFAULT_STATUSES)),
    )
    applied: Literal["mine", "branch"] = "branch" if scope is CalendarScope.branch else "mine"
    return criteria, applied, tz


async def get_calendar_feed(
    tenant_db: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    date_range: CalendarDateRange,
    scope: CalendarScope,
    statuses: list[InvitationStatus] | None,
    x_branch_id: uuid.UUID | None,
    per_day_limit: int | None = None,
) -> CalendarFeedOut:
    """Backs `GET /invitations/calendar` (specs/invitation-calendar).
    `per_day_limit` keeps only each day's first N events; `days` totals
    stay exact either way, and the rest of a day is paged through
    `get_calendar_day_page`.
    """
    criteria, applied, tz = await _calendar_criteria(
        tenant_db,
        tenant,
        user,
        date_from=date_range.date_from,
        date_to=date_range.date_to,
        scope=scope,
        statuses=statuses,
        x_branch_id=x_branch_id,
    )
    repository = InvitationRepository(tenant_db)
    totals = await repository.calendar_day_totals(criteria)
    rows = await repository.calendar_events(
        criteria, limit=CALENDAR_EVENT_LIMIT + 1, per_day_limit=per_day_limit
    )
    truncated = len(rows) > CALENDAR_EVENT_LIMIT
    if truncated:
        logger.info(
            "calendar_feed_truncated",
            date_from=date_range.date_from.isoformat(),
            date_to=date_range.date_to.isoformat(),
            total=sum(totals.values()),
        )

    span = (date_range.date_to - date_range.date_from).days + 1
    days = [date_range.date_from + timedelta(days=offset) for offset in range(span)]
    return CalendarFeedOut(
        scope=applied,
        timezone=display_tz_name(tz),
        date_from=date_range.date_from,
        date_to=date_range.date_to,
        generated_at=datetime.now(UTC),
        days=[CalendarDayOut(day=day, total=totals.get(day, 0)) for day in days],
        events=[CalendarEventOut.model_validate(dict(row)) for row in rows[:CALENDAR_EVENT_LIMIT]],
        truncated=truncated,
    )


async def get_calendar_day_page(
    tenant_db: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    day: date,
    scope: CalendarScope,
    statuses: list[InvitationStatus] | None,
    x_branch_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[CalendarEventOut], int, Literal["mine", "branch"]]:
    """Backs `GET /invitations/calendar/day`: one day's events a page at a
    time, with the feed's exact scope, filters and order — so page 1 of
    size N is the feed's first N for that day (design.md A3). The total is
    the same per-day count the feed reports.
    """
    criteria, applied, _ = await _calendar_criteria(
        tenant_db,
        tenant,
        user,
        date_from=day,
        date_to=day,
        scope=scope,
        statuses=statuses,
        x_branch_id=x_branch_id,
    )
    repository = InvitationRepository(tenant_db)
    total = (await repository.calendar_day_totals(criteria)).get(day, 0)
    rows = await repository.calendar_day_page(
        criteria, offset=(page - 1) * page_size, limit=page_size
    )
    return [CalendarEventOut.model_validate(dict(row)) for row in rows], total, applied


async def is_invitation_relevant_to(
    tenant_db: AsyncSession,
    invitation_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    default_host_role_id: uuid.UUID,
) -> bool:
    return await InvitationRepository(tenant_db).is_relevant_to(
        invitation_id, user_id=user_id, default_host_role_id=default_host_role_id
    )


async def _build_prefill(invitation: Invitation, user: User) -> InvitationLookupPrefillOut:
    """`photo_url` is resolved unconditionally; `id_proof_url` only when
    `user` holds `documents:view` at the matched invitation's branch — same
    split `router.py::_to_invitation_detail_out` uses for the staff detail
    view (add-invitation-lookup-by-email/design.md "photoUrl unconditional,
    idProofUrl gated...").
    """
    include_documents = user.has_permission("documents:view", invitation.branch_id)
    photo_key = invitation.primary_contact_photo_storage_key
    id_proof_key = invitation.primary_contact_id_proof_storage_key
    return InvitationLookupPrefillOut(
        full_name=invitation.primary_contact_full_name,
        email=invitation.primary_contact_email,
        phone=invitation.primary_contact_phone,
        preferred_contact_method=invitation.primary_contact_preferred_contact_method,
        visitor_category_id=invitation.visitor_category_id,
        id_proof_type=invitation.primary_contact_id_proof_type,
        photo_url=await storage_url_for(photo_key) if photo_key is not None else None,
        id_proof_url=(
            await storage_url_for(id_proof_key)
            if include_documents and id_proof_key is not None
            else None
        ),
    )


async def get_prefill_by_email(
    tenant_db: AsyncSession, email: str, branch_scope: BranchScope, user: User
) -> InvitationLookupPrefillOut | None:
    """Backs `GET /invitations/lookup-by-email`
    (`add-invitation-lookup-by-email/proposal.md`) — `None` on no match is
    the normal, expected case, not an error (spec.md "No Matching
    Invitation Returns Null Data, Not an Error")."""
    invitation = await InvitationRepository(tenant_db).get_latest_for_prefill_by_email(
        email, branch_scope
    )
    if invitation is None:
        return None
    return await _build_prefill(invitation, user)


async def get_prefill_by_phone(
    tenant_db: AsyncSession, phone_digits_value: str, branch_scope: BranchScope, user: User
) -> InvitationLookupPrefillOut | None:
    """Backs `GET /invitations/lookup-by-phone`
    (`reception-phone-prefill-lookup/proposal.md`); `phone_digits_value` is
    already normalized by the router. Logs the masked phone only."""
    invitation = await InvitationRepository(tenant_db).get_latest_for_prefill_by_phone(
        phone_digits_value, branch_scope
    )
    logger.info(
        "invitation_prefill_lookup_by_phone",
        phone=f"***{phone_digits_value[-2:]}",
        matched=invitation is not None,
    )
    if invitation is None:
        return None
    return await _build_prefill(invitation, user)


async def email_qr_png(schema_name: str, invitation_id: uuid.UUID) -> bytes | None:
    """The check-in QR a confirmation/reschedule email references by URL
    (serve-email-images-by-url-and-complete-contact design.md Decision 1),
    rendered from the token persisted at approval — the same bytes the
    email used to embed. `None` when the invitation or its QR row doesn't
    exist. The caller has already verified the URL signature; the schema
    comes from the signed tenant id, never the raw request.
    """
    async with tenant_session_scope(schema_name) as session:
        repository = InvitationRepository(session)
        if await repository.get(invitation_id) is None:
            return None
        qr_code = await repository.get_qr_code(invitation_id)
    if qr_code is None:
        return None
    return await generate_qr_png(qr_code.qr_token)


class ClearInProgressError(Exception):
    """A clear-all or retention purge already holds this tenant's lock."""


async def request_clear_invitations(
    tenant: Tenant, user: User, payload: ClearInvitationsRequest
) -> ClearInvitationsOut:
    """Validation already happened in the request schema; this best-effort
    pre-checks the lock (the task re-acquires it with `SET NX`, so
    correctness never depends on this check) and enqueues the delete.
    """
    redis = await get_redis()
    if await redis.exists(tasks.purge_lock_key(str(tenant.id))):
        raise ClearInProgressError
    from_date, to_date = payload.resolved_range()
    tasks.clear_tenant_invitations.delay(
        tenant_id=str(tenant.id),
        tenant_schema=tenant.schema_name,
        actor_user_id=str(user.id),
        include_checked_in=payload.include_checked_in,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        request_id=current_request_id(),
    )
    logger.info(
        "invitations_clear_requested",
        actor_user_id=str(user.id),
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
    )
    return ClearInvitationsOut(
        accepted=True,
        from_date=from_date,
        to_date=to_date,
        include_checked_in=payload.include_checked_in,
    )
