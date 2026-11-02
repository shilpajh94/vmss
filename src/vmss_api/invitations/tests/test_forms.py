"""Form-builder integration: visit info ids, requiredness, custom fields."""

import uuid
from collections.abc import Callable

import pytest
import structlog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    VisitPurposeFactory,
)
from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.auth.models import Permission, User, UserBranchRole
from vmss_api.auth.repository import RoleRepository
from vmss_api.invitations import tasks
from vmss_api.invitations.models import (
    Invitation,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.tests.helpers import (
    _add_consent,
    _answers,
    _configure_and_publish_branch_field,
    _create_and_publish_custom_field,
    _create_invitation,
    _create_invitation_raw,
    _create_invitation_success,
    _group_payload,
    _individual_payload,
    _login,
    _record_live_consent_field_ids,
    _remove_default_consent,
)
from vmss_api.org_structure.models import Branch, Department
from vmss_api.tenant.models import Tenant
from vmss_api.visit_info.models import VisitDuration, VisitPurpose

# --- visit-info-lookup-api: optional purposeId/hostId/durationId/departmentId -


async def test_create_invitation_with_no_ids_behaves_exactly_as_before(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """spec.md "Submission with no ids behaves exactly as before"."""
    data = await _create_invitation_success(
        client, await _login(client, user.email), branch, payload=_individual_payload()
    )
    assert data["registrationType"] == "individual"


async def test_create_invitation_with_ids_overwrites_free_text_with_canonical_value(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_purpose: VisitPurpose,
    visit_duration: VisitDuration,
    visit_department: Department,
) -> None:
    """spec.md "Submission with an id overwrites free text with the catalog
    value" — a mismatched free-text string is discarded in favor of the
    referenced row's canonical name. `hostId`/`durationId`/`departmentId`
    used to include a host id too, but the host is never client-resolved
    anymore (role-based-invitation-workflow) — see the dedicated
    `test_create_invitation_ignores_supplied_host_fields` below for that.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeOfVisit"] = "does not match the catalog row"
    payload["visitDetails"]["expectedDuration"] = "nor this"
    payload["visitDetails"]["departmentToVisit"] = "nor this either"
    payload["visitDetails"]["purposeId"] = str(visit_purpose.id)
    payload["visitDetails"]["durationId"] = str(visit_duration.id)
    payload["visitDetails"]["departmentId"] = str(visit_department.id)

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.purpose_of_visit == visit_purpose.name
    assert invitation.expected_duration == visit_duration.name
    assert invitation.department_to_visit == visit_department.name
    assert invitation.purpose_id == visit_purpose.id
    assert invitation.duration_id == visit_duration.id
    assert invitation.department_id == visit_department.id


async def test_create_invitation_ignores_supplied_host_fields(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
) -> None:
    """spec.md "A supplied hostId or hostNameOrEmail is silently ignored" —
    an un-updated client supplying either field no longer resolves a host or
    fails the request; the invitation is created with no host at all.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    payload["visitDetails"]["hostNameOrEmail"] = visit_host.full_name

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.host_id is None
    assert invitation.host_name_or_email is None


async def test_create_invitation_with_no_department_succeeds_and_leaves_it_unset(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """allow-optional-department-at-creation spec.md "Submission with no
    department succeeds and leaves it unset" — a visitor or staff member
    creating an invitation often doesn't know the receiving organisation's
    internal department, so omitting both `departmentToVisit` and
    `departmentId` no longer fails the request.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload["visitDetails"]["departmentToVisit"]

    data = await _create_invitation_success(client, token, branch, payload=payload)

    invitation = await InvitationRepository(db_session).get_by_tracking_id(data["trackingId"])
    assert invitation is not None
    assert invitation.department_to_visit is None
    assert invitation.department_id is None


async def test_create_invitation_never_enqueues_host_email(
    client: AsyncClient,
    user: User,
    branch: Branch,
    visit_host: User,
    monkeypatch,
) -> None:
    """REMOVED spec.md requirement "Invitation Creation Notifies the
    Resolved Host via Email" (role-based-invitation-workflow) — a host is
    never resolved at creation anymore, whether or not a client still
    supplies `hostId`, so this dispatch never fires at creation. See the
    `approvals` capability's "Delegating the Ownership Step Also Resolves
    the Invitation's Host" for the email the actual host now receives
    instead, once delegated.
    """
    calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_host_creation_notification, "delay", lambda **kw: calls.append(kw)
    )

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["hostId"] = str(visit_host.id)
    await _create_invitation_success(client, token, branch, payload=payload)

    assert calls == []


async def test_created_invitation_current_step_id_is_directly_actionable(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_host: User,
    issue_token: Callable[[User], str],
) -> None:
    """add-approval-step-id-and-host-routing — `currentApprovalStep.id` on
    the creation response is the same id `POST /invitations/{id}/approval-
    steps/{stepId}/approve` expects, with no separate lookup needed. Every
    newly created invitation's ownership step is role-identified for the
    tenant's default host role (role-based-invitation-workflow), so a
    holder of that role — e.g. Reception — is the current approver and may
    approve it directly like any other step (`specs/approvals/spec.md`
    "The Ownership Step Is a Plain Role-Identified Step, Approvable
    Directly"). This invitation's category has no configured workflow rules,
    so this one synthetic step is also its *only* step — a single-step,
    reception-only workflow — so approving it directly resolves `hostId` to
    the approving Reception user (see "Approving the Only Step of a
    Single-Step Workflow Also Resolves the Invitation's Host"), the same as
    delegating would.
    """
    # `_default_host_role` (this module's autouse fixture) seeds "reception"
    # with no permissions attached — enough for snapshot logic, not enough
    # to actually approve — so this test grants `invitations:approve` on it
    # explicitly, reusing the global permission row the `user` fixture's
    # own admin permission set already created.
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    permission = (
        await db_session.execute(select(Permission).where(Permission.code == "invitations:approve"))
    ).scalar_one()
    reception_role.permissions.append(permission)
    # Append in-memory too, not just `session.add()` — see
    # `approvals/tests.py::_grant_approve_permission`'s docstring for why
    # the test session's `expire_on_commit=False` makes this necessary.
    branch_role = UserBranchRole(
        id=uuid.uuid4(), user_id=visit_host.id, role_id=reception_role.id, branch_id=branch.id
    )
    visit_host.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    assert data["hostId"] is None
    assert data["currentApprovalStep"] is not None
    step_id = data["currentApprovalStep"]["id"]
    assert data["currentApprovalStep"]["approverRoleId"] == str(reception_role.id)
    assert data["currentApprovalStep"]["approverUserId"] is None

    host_token = issue_token(visit_host)
    response = await client.post(
        f"/api/v1/invitations/{data['id']}/approval-steps/{step_id}/approve",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"
    assert response.json()["data"]["hostId"] == str(visit_host.id)


async def test_create_invitation_unknown_purpose_id_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Unknown or cross-tenant id is rejected"."""
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeId"] = str(uuid.uuid4())

    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422

    invitations = await InvitationRepository(db_session).list()
    assert invitations == []


async def test_create_invitation_inactive_department_id_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    visit_department: Department,
) -> None:
    visit_department.is_active = False
    db_session.add(visit_department)
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["departmentId"] = str(visit_department.id)

    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_cross_tenant_purpose_id_rejected(
    client: AsyncClient,
    user: User,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2's tenant-isolation case: a `purposeId` valid
    in a different tenant's schema must not resolve here.
    """
    other_schema = "tenant_other_test_visit_info"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_purpose = VisitPurposeFactory.build(id=uuid.uuid4(), name="Other Tenant Purpose")
        other_session.add(other_purpose)
        await other_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitDetails"]["purposeId"] = str(other_purpose.id)

    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_walk_in_registration_visit_details_submit_exposes_id_fields() -> None:
    """spec.md "Walk-in registration inherits the same optional fields" —
    guards against a future refactor breaking `registrations.schemas`'s
    re-export of the shared `VisitDetailsSubmit` class (task 6.3).
    """
    from vmss_api.registrations.schemas import VisitDetailsSubmit as WalkInVisitDetailsSubmit

    assert set(WalkInVisitDetailsSubmit.model_fields) >= {
        "purpose_id",
        "host_id",
        "duration_id",
        "department_id",
    }


# --- form-builder integration: branch-configured requiredness ---------------


async def test_create_invitation_id_proof_not_required_when_branch_deactivates_it(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "ID proof not required when the
    branch has deactivated it".
    """
    token = await _login(client, user.email)
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="id_proof_upload",
        changes={"isActive": False, "isRequired": False},
    )

    payload = _individual_payload()
    del payload["primaryContact"]["idProofType"]
    response = await _create_invitation_raw(
        client, token, branch, payload=payload, include_primary_id_proof=False
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("blank", ["", "null", " NULL "])
def test_blank_id_proof_type_is_normalized_to_none(blank: str) -> None:
    """`idProofType` is optional: `""`/`"null"` mean "not provided" for both
    the create-invitation and walk-in payloads (shared schemas).
    """
    from vmss_api.invitations.schemas import InvitationPrimaryContactCreate, VisitorSubmit

    assert (
        InvitationPrimaryContactCreate(
            full_name="A", email="a@example.com", id_proof_type=blank
        ).id_proof_type
        is None
    )
    assert (
        VisitorSubmit(full_name="A", email="a@example.com", id_proof_type=blank).id_proof_type
        is None
    )


async def test_create_invitation_photo_not_required_when_branch_deactivates_it(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Missing primary contact photo is
    accepted when the branch has deactivated it".
    """
    token = await _login(client, user.email)
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="profile_photo",
        changes={"isActive": False, "isRequired": False},
    )

    response = await _create_invitation_raw(
        client, token, branch, payload=_individual_payload(), include_primary_photo=False
    )
    assert response.status_code == 201, response.text


async def test_create_invitation_consent_not_required_when_branch_deactivates_it(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and
    Recorded" — a consent the branch no longer marks required may be
    omitted.
    """
    token = await _login(client, user.email)
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="consent_agreement",
        field_key="safety_guidelines_accepted",
        changes={"isRequired": False},
    )

    payload = _individual_payload()
    _remove_default_consent(payload, "safety_guidelines_accepted")
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text


async def test_create_invitation_expected_duration_optional(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """ "Expected Duration" is no longer collected by either visitor-facing
    wizard at all (make-expected-duration-optional), so `create_invitation`
    must accept a submission that omits it regardless of the branch's own
    Form Builder configuration for the field — unlike ID proof/photo, there
    is no requiredness check for it any more.
    """
    token = await _login(client, user.email)
    payload = _individual_payload()
    del payload["visitDetails"]["expectedDuration"]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text

    tracking_id = response.json()["data"]["trackingId"]
    track_response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": tracking_id}
    )
    assert track_response.status_code == 200, track_response.text
    assert track_response.json()["data"]["expectedDuration"] is None


async def test_create_invitation_carried_item_allowed_when_branch_adds_custom_item(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    Optional Structured Declarations" — a key the branch adds to its
    Carried Items options becomes acceptable.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    step = next(s for s in steps_response.json()["data"] if s["key"] == "carried_items")
    field = next(f for f in step["fields"] if f["key"] == "items")

    patch_response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}",
        json={"options": [*field["options"], "company_badge"]},
        headers=headers,
    )
    assert patch_response.status_code == 200, patch_response.text
    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["company_badge"]}
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 201, response.text


async def test_create_invitation_carried_item_still_rejected_when_not_in_branch_config(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Sibling of the success case above — a key that was never added to
    the branch's Carried Items options is still rejected even after that
    branch has published its own configuration (not just the tenant
    default fallback).
    """
    token = await _login(client, user.email)
    # Gives this branch its own published configuration (distinct from the
    # tenant-default fallback) via an innocuous field edit, so this test
    # exercises the branch's own resolved config, not just the default.
    await _configure_and_publish_branch_field(
        client,
        token,
        branch,
        step_key="visitor_info",
        field_key="profile_photo",
        changes={"placeholder": "A clear, recent photo"},
    )

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["not_a_configured_item"]}
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_captures_primary_contact_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _individual_payload()
    # The primary contact's Visitor Info-step answers are sourced from the
    # invitation-level `customFields` array, not a nested
    # `primaryContact.customFields` — see `InvitationPrimaryContactCreate`'s
    # docstring in `schemas.py`.
    payload["customFields"] = [{"fieldId": field["id"], "value": "E-1001"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert _answers(detail_response.json()["data"]["customFields"]) == [
        {"fieldId": field["id"], "value": "E-1001"}
    ]


async def test_create_invitation_captures_primary_contact_custom_field_on_system_group(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """An admin-authored custom field can be attached to the seeded
    (system) "visitors" group on Visitor Info — that group is never
    surfaced by `custom_groups_for_invitation_scope`/`custom_groups_for_step`
    (its cardinality is the `visitors` payload list's own length, not a
    `groups` entry), so such a field's answer must still be accepted
    through the ordinary per-visitor `customFields` array, the same as
    an ungrouped field. Regression test: `custom_fields_for_step` used to
    exclude any field with a `groupId`, including one on this system group,
    which meant the field's answer was rejected as unknown no matter which
    payload array it was submitted through.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == "visitor_info")
    [visitors_group] = step["groups"]
    assert visitors_group["key"] == "visitors"
    assert visitors_group["isSystem"] is True

    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "purpose_note",
            "label": "Purpose Note",
            "fieldType": "text",
            "groupId": visitors_group["id"],
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    field_id = create_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field_id, "value": "some value"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert _answers(detail_response.json()["data"]["customFields"]) == [
        {"fieldId": field_id, "value": "some value"}
    ]


async def test_create_invitation_captures_co_visitor_custom_fields_independently(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Two visitors answering the same admin-authored Visitor Info field
    each keep their own independent answer."""
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="employee_id"
    )

    payload = _group_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "E-1001"}]
    payload["visitors"][0]["customFields"] = [{"fieldId": field["id"], "value": "E-2002"}]
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    body = detail_response.json()["data"]
    assert _answers(body["customFields"]) == [{"fieldId": field["id"], "value": "E-1001"}]
    visitors_by_name = {v["fullName"]: v for v in body["visitors"]}
    assert _answers(visitors_by_name["Alexander Pierce"]["customFields"]) == [
        {"fieldId": field["id"], "value": "E-2002"}
    ]
    assert _answers(visitors_by_name["Clara Oswald"]["customFields"]) == []


async def test_create_invitation_captures_vehicle_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="vehicle_info", key="parking_zone"
    )

    payload = _group_payload()
    payload["vehicles"][0]["customFields"] = [{"fieldId": field["id"], "value": "B2"}]
    data = await _create_invitation_success(
        client, token, branch, payload=payload, visitor_file_count=2
    )

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    vehicles = detail_response.json()["data"]["vehicles"]
    vehicles_by_plate = {v["licensePlate"]: v for v in vehicles}
    assert _answers(vehicles_by_plate["KA-01-AB-1234"]["customFields"]) == [
        {"fieldId": field["id"], "value": "B2"}
    ]
    assert vehicles_by_plate["KA-05-CD-5678"]["customFields"] == []


async def test_create_invitation_captures_invitation_level_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A custom field on Visit Details (no per-entity structure of its own)
    is captured once per invitation."""
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center"
    )

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "CC-42"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert _answers(detail_response.json()["data"]["customFields"]) == [
        {"fieldId": field["id"], "value": "CC-42"}
    ]


async def test_create_invitation_custom_field_unresolvable_id_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": str(uuid.uuid4()), "value": "x"}]
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_custom_field_missing_required_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center", is_required=True
    )

    payload = _individual_payload()
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_hidden_label_custom_field_missing_required_rejected(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """update-form-field-hide-label-option: `hideLabel` is a display-only
    property — a required field with its label hidden still rejects a
    missing submitted value the same way an always-visible required field
    does."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="visit_details",
        key="cost_center",
        is_required=True,
        hide_label=True,
    )

    payload = _individual_payload()
    response = await _create_invitation(client, token, branch, payload=payload)
    assert response.status_code == 422


async def test_create_invitation_static_text_field_needs_no_submitted_value(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """specs/form-builder/spec.md (delta) "A `static_text` Field Renders
    Admin-Authored Content With No Input Control" — a `static_text` field
    (e.g. a Terms & Conditions block admin-authored on Visit Details)
    collects no answer, so an invitation created without any submitted
    value for its key must still succeed."""
    token = await _login(client, user.email)
    await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="visit_details",
        key="visit_notice",
        field_type="static_text",
        help_text="Please arrive 10 minutes early.",
    )

    payload = _individual_payload()
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]


async def test_create_invitation_seeded_carried_items_field_unaffected_by_custom_field(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression: adding an admin-authored field to Carried Items must not
    disturb the seeded `items` field's existing wire shape (`carriedItems.
    items`, mapped to the `carried_items` column) — only the new field's
    answer routes through `customFields`."""
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="carried_items",
        key="company_badge",
        field_type="toggle_switch",
    )

    payload = _individual_payload()
    payload["carriedItems"] = {"items": ["laptop_tablet"]}
    payload["customFields"] = [{"fieldId": field["id"], "value": True}]
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]

    detail_response = await client.get(
        f"/api/v1/invitations/{data['id']}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    body = detail_response.json()["data"]
    assert body["carriedItems"] == ["laptop_tablet"]
    assert _answers(body["customFields"]) == [{"fieldId": field["id"], "value": True}]


async def test_create_invitation_custom_consent_field_goes_through_consents(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """Regression for design.md Decision 6: a new admin-authored Consent
    Agreement field is already captured by the pre-existing `consents`
    array (every field on that step, system or not) - it must not also be
    required in `customFields`, and supplying it there instead of in
    `consents` must not satisfy the requirement.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client,
        token,
        branch,
        step_key="consent_agreement",
        key="extra_consent",
        field_type="toggle_switch",
        is_required=True,
    )

    payload = _individual_payload()
    _add_consent(payload, field["id"], True)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    assert data["id"]

    wrong_scope_payload = _individual_payload()
    wrong_scope_payload["customFields"] = [{"fieldId": field["id"], "value": True}]
    response = await _create_invitation(client, token, branch, payload=wrong_scope_payload)
    assert response.status_code == 422


async def test_create_invitation_custom_field_values_tenant_schema_isolation(
    client: AsyncClient,
    user: User,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2 tenant-isolation case: an invitation carrying
    custom field answers, created under this tenant's schema, must not be
    visible from a session bound to a different tenant's schema.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visit_details", key="cost_center"
    )
    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field["id"], "value": "CC-42"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    other_schema = "tenant_other_custom_field_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        result = await other_session.execute(
            select(Invitation).where(Invitation.tracking_id == data["trackingId"])
        )
        assert result.scalar_one_or_none() is None


async def test_create_invitation_missing_default_host_role_fails_as_server_misconfiguration(
    client: AsyncClient, user: User, branch: Branch, tenant: Tenant, db_session: AsyncSession
) -> None:
    """`auth/service.py`'s `update_role`/`delete_role` protect any
    `STANDARD_ROLE_NAMES` role (including "reception") from rename/delete
    via the API, so this provisioning-gap state — a tenant with no
    resolvable default host role — isn't reachable through the product's
    own API. It's constructed directly at the repository layer instead,
    per `design.md`'s "Risks/Trade-offs" note, bypassing that protection on
    purpose (not a scenario a client can trigger).
    """
    token = await _login(client, user.email)
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    await RoleRepository(db_session).soft_delete(reception_role)
    await db_session.commit()

    # `capture_logs()` disables every configured processor by default
    # (including `structlog.contextvars.merge_contextvars`), so a field
    # bound only via contextvars (`tenant_id`, here) has to have that
    # processor passed back in explicitly to show up in a captured entry.
    with capture_logs(processors=(structlog.contextvars.merge_contextvars,)) as captured:
        response = await _create_invitation(client, token, branch, payload=_individual_payload())

    assert response.status_code == 500

    [entry] = [e for e in captured if e["event"] == "default_host_role_not_seeded"]
    assert entry["log_level"] == "error"
    # tenant_id is bound into structlog's contextvars for every authenticated
    # request (core/tenancy.py) — no explicit parameter needed for this log
    # line to carry it (logging-observability.md §1).
    assert entry["tenant_id"] == str(tenant.id)

    # `create_invitation` calls `get_default_host_role` before
    # `tenant_db.commit()` (invitations/service.py), so nothing from this
    # failed attempt should have reached the database. The test client's
    # `get_tenant_db` override hands every request the same bare
    # `db_session` with no `async with` around it (unlike production's
    # `tenant_session_scope`), so this explicit rollback stands in for the
    # automatic rollback-on-exit production gets for free — see
    # `org_structure/tests.py`'s
    # `test_provision_branch_rolls_back_partial_tree_on_mid_transaction_conflict`.
    await db_session.rollback()
    for model in (Invitation, InvitationVisitor, InvitationVehicle, InvitationApprovalStep):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0, f"{model.__name__} row(s) leaked from a failed default-host-role lookup"


async def test_create_invitation_through_new_custom_step_with_and_without_fields(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}

    step_with_field = (
        await client.post(
            "/api/v1/form-builder/steps",
            json={"key": "custom_step_one", "name": "Custom Step"},
            headers=headers,
        )
    ).json()["data"]
    field_response = await client.post(
        f"/api/v1/form-builder/steps/{step_with_field['id']}/fields",
        json={"key": "custom_answer", "label": "Custom Answer", "fieldType": "text"},
        headers=headers,
    )
    assert field_response.status_code == 201, field_response.text

    # A second new custom step deliberately left with zero fields — must
    # not break `resolve_effective_form`/validation for a submission that
    # simply has nothing to answer on it.
    empty_step_response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "custom_step_two", "name": "Custom Step 2"},
        headers=headers,
    )
    assert empty_step_response.status_code == 201, empty_step_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    field_id = field_response.json()["data"]["id"]
    post_publish_steps = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert post_publish_steps.status_code == 200, post_publish_steps.text
    _record_live_consent_field_ids(post_publish_steps.json()["data"])

    payload = _individual_payload()
    payload["customFields"] = [{"fieldId": field_id, "value": "Some value"}]
    data = await _create_invitation_success(client, token, branch, payload=payload)

    detail_response = await client.get(f"/api/v1/invitations/{data['id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    assert _answers(detail_response.json()["data"]["customFields"]) == [
        {"fieldId": field_id, "value": "Some value"}
    ]
