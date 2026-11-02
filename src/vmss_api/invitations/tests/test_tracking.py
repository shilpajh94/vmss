"""Public tracking lookup, lookup by email, and reception prefill lookups."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import (
    ApprovalWorkflowRuleFactory,
    CompanyFactory,
    RoleFactory,
    VisitorCategoryFactory,
)
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.invitations.tests.helpers import (
    _DEFAULT_VISITOR_CATEGORY_ID,
    _branch_scoped_invitation_creator,
    _branch_scoped_invitation_creator_with_documents,
    _branch_scoped_invitation_viewer,
    _build_invitation,
    _create_and_publish_custom_field,
    _create_invitation_success,
    _custom_field_value,
    _group_payload,
    _individual_payload,
    _login,
    _lookup_by_phone,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

# --- API-12: public tracking lookup ------------------------------------------


async def test_track_by_tracking_id_individual_success(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "submitted"
    assert body["primaryContactFullName"] == "Meera Krishnan"
    assert body["visitors"] == []
    assert body["vehicles"] == []
    assert body["expectedDuration"] == "< 1 hour"
    assert body["departmentToVisit"] == "Human Resources"


async def test_track_by_tracking_id_masks_custom_file_upload_field_raw_storage_key(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """add-generic-custom-field-file-url-resolution, extended to the public
    tracking-lookup response — same posture as the QR/check-in-by-tracking-
    id counterparts: a `file_upload`-typed custom field's raw storage key
    must never reach this unauthenticated caller.
    """
    token = await _login(client, user.email)
    field = await _create_and_publish_custom_field(
        client, token, branch, step_key="visitor_info", key="pic", field_type="file_upload"
    )
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_custom_field_values={
            field["id"]: "vmss:tenant:invitations/custom-fields:primary-pic.jpg"
        },
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": invitation.tracking_id}
    )
    assert response.status_code == 200
    assert _custom_field_value(response.json()["data"]["customFields"], field["id"]) is None


async def test_track_by_tracking_id_group_success(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "submitted"
    assert len(body["visitors"]) == 2
    assert len(body["vehicles"]) == 2
    assert body["carriedItems"] == ["laptop_tablet", "mobile_phone"]
    assert body["carriedItemsDescription"] == "2 laptops"


async def test_track_by_tracking_id_omits_current_step_for_auto_approved_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Non-workflow invitation omits step progress" — an
    auto-approved invitation is never `submitted` and has no snapshotted
    steps at all (role-based-invitation-workflow: every *submitted*
    invitation now gets an unconditional ownership step, but an
    auto-approved one skips snapshotting entirely — see "Auto-Approved
    Invitations Are Never Snapshotted").
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), auto_approve_pre_registered_visitors=True))
    await db_session.commit()

    token = await _login(client, user.email)
    data = await _create_invitation_success(client, token, branch, payload=_individual_payload())
    assert data["status"] == "approved"

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["currentApprovalStep"] is None


async def test_track_by_tracking_id_exposes_current_step_for_workflow_backed_invitation(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitation-multi-step-approval spec.md "Workflow-backed invitation
    exposes current step progress" — a category with two active rules
    snapshots exactly those two steps at submission (no separate ownership
    step ahead of them — see `docs/features/approvals.md` "The
    host-nomination step"); the tracking lookup surfaces the first
    configured step (`stepOrder` 1) as current, since it's the first to
    become pending and doubles as the host-nomination step.
    """
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Workflow Category", code="WORKFLOW-CAT"
    )
    approver_role = RoleFactory.build(id=uuid.uuid4(), name="step-one-approver", permissions=[])
    db_session.add_all([category, approver_role])
    await db_session.flush()
    db_session.add_all(
        [
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=1,
                approver_role_id=approver_role.id,
            ),
            ApprovalWorkflowRuleFactory.build(
                id=uuid.uuid4(),
                visitor_category_id=category.id,
                step_order=2,
                approver_role_id=approver_role.id,
            ),
        ]
    )
    await db_session.commit()

    token = await _login(client, user.email)
    payload = _individual_payload()
    payload["visitorCategoryId"] = str(category.id)
    data = await _create_invitation_success(client, token, branch, payload=payload)
    steps = await InvitationApprovalStepRepository(db_session).list_for_invitation(
        uuid.UUID(data["id"])
    )
    step_one = next(s for s in steps if s.step_order == 1)
    assert data["currentApprovalStep"] == {
        "id": str(step_one.id),
        "stepOrder": 1,
        "approverRoleId": str(approver_role.id),
        "approverUserId": None,
        "totalSteps": 2,
        "delegatedToUserId": None,
    }

    response = await client.get(
        "/api/v1/invitations/track", params={"trackingId": data["trackingId"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["currentApprovalStep"] == {
        "id": str(step_one.id),
        "stepOrder": 1,
        "approverRoleId": str(approver_role.id),
        "approverUserId": None,
        "totalSteps": 2,
        "delegatedToUserId": None,
    }


async def test_track_unknown_tracking_id_not_found(client: AsyncClient, tenant: Tenant) -> None:
    response = await client.get("/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"})
    assert response.status_code == 404


async def test_track_requires_exactly_one_param(client: AsyncClient, tenant: Tenant) -> None:
    response = await client.get("/api/v1/invitations/track")
    assert response.status_code == 422

    response = await client.get(
        "/api/v1/invitations/track",
        params={"trackingId": "INV-DEADBEEF", "email": "a@example.com"},
    )
    assert response.status_code == 422


async def test_track_by_email_minimal_disclosure(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=_group_payload(), visitor_file_count=2
    )

    response = await client.get(
        "/api/v1/invitations/track", params={"email": "priya.sharma@enterprise-ugo.co"}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body) == 1
    assert set(body[0].keys()) == {"trackingId", "status"}
    assert body[0]["trackingId"] == data["trackingId"]


async def test_track_rate_limit_trips(client: AsyncClient, tenant: Tenant, monkeypatch) -> None:
    """`slowapi`'s `Limiter` is disabled outright in the test environment
    (`core/rate_limit.py`: `enabled=settings.environment != "test"`) — flipped
    on here for just this one test to exercise the 429 path
    (security-architecture.md §2), then restored.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.get("/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"})
        for _ in range(25)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_track_unresolvable_default_tenant_logged_as_error(
    client: AsyncClient, monkeypatch
) -> None:
    """`track_default_tenant_db` (`invitations/deps.py`) resolves the single
    configured default tenant via `core.tenancy.resolve_default_tenant`. When
    that tenant doesn't exist, this is a server-side misconfiguration, not a
    caller error, so it must be logged at `ERROR` with the same
    not-found/inactive distinction `registrations/deps.py`'s equivalent
    fallback already has — see
    harden-default-tenant-resolution-and-readiness/design.md. The
    client-facing 404 is unchanged from before this consistency fix.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "no-such-tenant-slug")

    with capture_logs() as captured:
        response = await client.get(
            "/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"}
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not found or inactive"

    [entry] = [e for e in captured if e["event"] == "invitations_track_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "not_found"


async def test_track_inactive_default_tenant_logged_as_error(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession
) -> None:
    await db_session.execute(update(Tenant).where(Tenant.id == tenant.id).values(is_active=False))
    await db_session.commit()

    with capture_logs() as captured:
        response = await client.get(
            "/api/v1/invitations/track", params={"trackingId": "INV-DEADBEEF"}
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not found or inactive"

    [entry] = [e for e in captured if e["event"] == "invitations_track_default_tenant_unconfigured"]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "inactive"


# --- add-invitation-lookup-by-email ------------------------------------------


async def test_lookup_by_email_returns_most_recent_invitations_prefill_data(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    identifier = "jane@example.com"
    older = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email=identifier,
        primary_contact_full_name="J Doe",
        tracking_id="INV-LOOKUP-OLD1",
    )
    newer = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email=identifier,
        primary_contact_full_name="Jane Doe",
        primary_contact_phone="1234567890",
        primary_contact_preferred_contact_method="email",
        primary_contact_id_proof_type="passport",
        visitor_category_id=_DEFAULT_VISITOR_CATEGORY_ID,
        tracking_id="INV-LOOKUP-NEW1",
    )
    db_session.add_all([older, newer])
    await db_session.commit()
    now = datetime.now(UTC)
    newer.created_at = now
    older.created_at = now - timedelta(days=1)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": identifier},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["fullName"] == "Jane Doe"
    assert data["phone"] == "1234567890"
    assert data["preferredContactMethod"] == "email"
    assert data["idProofType"] == "passport"
    assert data["visitorCategoryId"] == str(_DEFAULT_VISITOR_CATEGORY_ID)


async def test_lookup_by_email_is_case_insensitive(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    invitation = _build_invitation(db_session, branch.id, primary_contact_email="Jane@Example.com")
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "jane@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is not None


async def test_lookup_by_email_no_match_returns_null_data(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "no-such-visitor@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_email_match_at_unauthorized_branch_returns_null(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-LOOKUP-1")
    db_session.add(other_branch)
    await db_session.flush()

    invitation = _build_invitation(
        db_session, other_branch.id, primary_contact_email="only-at-other-branch@example.com"
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "only-at-other-branch@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_email_branch_header_excludes_matching_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-LOOKUP-2")
    db_session.add(other_branch)
    await db_session.flush()

    invitation = _build_invitation(
        db_session, other_branch.id, primary_contact_email="multi-branch-caller@example.com"
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    branch_role = UserBranchRole(
        id=uuid.uuid4(), role=creator.branch_roles[0].role, branch_id=other_branch.id
    )
    creator.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "multi-branch-caller@example.com"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_email_requires_invitations_create_permission(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    """A caller holding only `invitations:view` (not `invitations:create`)
    is rejected — this lookup only exists to prefill the create flow
    (add-invitation-lookup-by-email/design.md "Permission").
    """
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "anyone@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_lookup_by_email_photo_url_resolved_without_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "Photo URL Is Always Resolved When Captured" — a face photo
    isn't gated like an identity document in this codebase."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email="has-documents@example.com",
        primary_contact_id_proof_storage_key="docs/id.jpg",
        primary_contact_photo_storage_key="docs/photo.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "has-documents@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["photoUrl"] is not None


async def test_lookup_by_email_id_proof_url_null_without_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "ID-proof URL Is Null Without documents:view"."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email="has-id-proof@example.com",
        primary_contact_id_proof_type="Passport",
        primary_contact_id_proof_storage_key="docs/id.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "has-id-proof@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["idProofType"] is not None
    assert data["idProofUrl"] is None


async def test_lookup_by_email_id_proof_url_resolved_with_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """spec.md "ID-proof URL Is Resolved With documents:view"."""
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_email="has-id-proof-2@example.com",
        primary_contact_id_proof_storage_key="docs/id.jpg",
    )
    db_session.add(invitation)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator_with_documents(db_session, tenant, branch.id)
    token = issue_token(creator)
    response = await client.get(
        "/api/v1/invitations/lookup-by-email",
        params={"email": "has-id-proof-2@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["idProofUrl"] is not None


async def test_list_invitations_filters_by_status_registration_type_and_source(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    matching = _build_invitation(
        db_session,
        branch.id,
        status="submitted",
        registration_type="group",
        source="visitor_walk_in",
    )
    non_matching = _build_invitation(
        db_session,
        branch.id,
        status="cancelled",
        registration_type="individual",
        source="staff_pre_registration",
    )
    db_session.add_all([matching, non_matching])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={
            "status": "submitted",
            "registrationType": "group",
            "source": "visitor_walk_in",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert matching.tracking_id in tracking_ids
    assert non_matching.tracking_id not in tracking_ids


async def test_list_invitations_filters_by_search_matching_contact_name_or_tracking_id(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    jane = _build_invitation(db_session, branch.id, primary_contact_full_name="Jane Visitor")
    john = _build_invitation(db_session, branch.id, primary_contact_full_name="John Guest")
    db_session.add_all([jane, john])
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    name_response = await client.get(
        "/api/v1/invitations", params={"search": "jane"}, headers=headers
    )
    assert name_response.status_code == 200
    name_tracking_ids = {row["trackingId"] for row in name_response.json()["data"]}
    assert jane.tracking_id in name_tracking_ids
    assert john.tracking_id not in name_tracking_ids

    id_response = await client.get(
        "/api/v1/invitations", params={"search": john.tracking_id}, headers=headers
    )
    assert id_response.status_code == 200
    id_tracking_ids = {row["trackingId"] for row in id_response.json()["data"]}
    assert john.tracking_id in id_tracking_ids
    assert jane.tracking_id not in id_tracking_ids


async def test_list_invitations_filters_by_purpose_of_visit(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """specs/invitations/spec.md "Invitation List Supports a Purpose-of-Visit
    Filter" — exact match, reflected in `pagination.total`.
    """
    purpose = f"Interview {uuid.uuid4().hex[:8]}"
    matching = _build_invitation(db_session, branch.id, purpose_of_visit=purpose)
    non_matching = _build_invitation(db_session, branch.id, purpose_of_visit="Delivery")
    db_session.add_all([matching, non_matching])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": purpose},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["trackingId"] for row in body["data"]] == [matching.tracking_id]
    assert body["pagination"]["total"] == 1


async def test_list_invitations_purpose_filter_combines_with_status(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    purpose = f"Interview {uuid.uuid4().hex[:8]}"
    submitted = _build_invitation(
        db_session, branch.id, purpose_of_visit=purpose, status="submitted"
    )
    approved = _build_invitation(db_session, branch.id, purpose_of_visit=purpose, status="approved")
    db_session.add_all([submitted, approved])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": purpose, "status": "submitted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert [row["trackingId"] for row in response.json()["data"]] == [submitted.tracking_id]


async def test_list_invitations_purpose_filter_requires_exact_match(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    purpose = f"Interview {uuid.uuid4().hex[:8]}"
    invitation = _build_invitation(db_session, branch.id, purpose_of_visit=purpose)
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": purpose[:-1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_purpose_filter_rejects_over_long_value(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"purposeOfVisit": "x" * 256},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "status_value", ["submitted", "approved", "denied", "checked_in", "checked_out"]
)
async def test_list_invitations_filters_by_each_status_value(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    status_value: str,
) -> None:
    """api-conventions.md §1 — `InvitationStatus` is a closed enum covering
    every value `Invitation.status`'s state-machine writes ever produce
    (schemas.py's `InvitationStatus` docstring); this proves each one
    actually round-trips through the `status` query param, not just
    "submitted" the way the combined filter test above does.
    """
    other_status = "approved" if status_value != "approved" else "submitted"
    matching = _build_invitation(db_session, branch.id, status=status_value)
    non_matching = _build_invitation(db_session, branch.id, status=other_status)
    db_session.add_all([matching, non_matching])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"status": status_value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert matching.tracking_id in tracking_ids
    assert non_matching.tracking_id not in tracking_ids


async def test_list_invitations_invalid_status_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"status": "cancelled"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_list_invitations_sort_order(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    older = _build_invitation(db_session, branch.id, submitted_at=now - timedelta(hours=1))
    newer = _build_invitation(db_session, branch.id, submitted_at=now)
    db_session.add_all([older, newer])
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    default_order = await client.get("/api/v1/invitations", headers=headers)
    default_ids = [row["trackingId"] for row in default_order.json()["data"]]
    assert default_ids.index(newer.tracking_id) < default_ids.index(older.tracking_id)

    asc_order = await client.get(
        "/api/v1/invitations", params={"sortOrder": "asc"}, headers=headers
    )
    asc_ids = [row["trackingId"] for row in asc_order.json()["data"]]
    assert asc_ids.index(older.tracking_id) < asc_ids.index(newer.tracking_id)


async def test_list_invitations_invalid_sort_by_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/invitations",
        params={"sortBy": "not_a_real_field"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# --- reception-phone-prefill-lookup ------------------------------------------


async def test_lookup_by_phone_returns_most_recent_invitations_prefill_data(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    older = _build_invitation(
        db_session,
        branch.id,
        primary_contact_phone="9544232271",
        primary_contact_email="old@example.com",
        primary_contact_full_name="J Doe",
        tracking_id="INV-PHONE-OLD1",
    )
    newer = _build_invitation(
        db_session,
        branch.id,
        primary_contact_phone="9544232271",
        primary_contact_email="jane@example.com",
        primary_contact_full_name="Jane Doe",
        primary_contact_id_proof_type="passport",
        tracking_id="INV-PHONE-NEW1",
    )
    db_session.add_all([older, newer])
    await db_session.commit()
    now = datetime.now(UTC)
    newer.created_at = now
    older.created_at = now - timedelta(days=1)
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "9544232271")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["fullName"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert data["idProofType"] == "passport"


async def test_lookup_by_phone_ignores_formatting_differences(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    db_session.add(
        _build_invitation(db_session, branch.id, primary_contact_phone="+91 95442-32271")
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "919544232271")
    assert response.status_code == 200
    assert response.json()["data"] is not None


async def test_lookup_by_phone_without_email_returns_null_email(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    db_session.add(
        _build_invitation(
            db_session, branch.id, primary_contact_phone="9876543210", primary_contact_email=None
        )
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "9876543210")
    assert response.status_code == 200
    assert response.json()["data"]["email"] is None


async def test_lookup_by_phone_no_match_returns_null_data(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "5550001111")
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_phone_too_few_digits_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "12-3")
    assert response.status_code == 422


async def test_lookup_by_phone_match_at_unauthorized_branch_returns_null(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-PHONE-1")
    db_session.add(other_branch)
    await db_session.flush()
    db_session.add(
        _build_invitation(db_session, other_branch.id, primary_contact_phone="4445556667")
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(creator), "4445556667")
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_phone_branch_header_excludes_matching_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-PHONE-2")
    db_session.add(other_branch)
    await db_session.flush()
    db_session.add(
        _build_invitation(db_session, other_branch.id, primary_contact_phone="3334445556")
    )
    await db_session.commit()

    creator = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    branch_role = UserBranchRole(
        id=uuid.uuid4(), role=creator.branch_roles[0].role, branch_id=other_branch.id
    )
    creator.branch_roles.append(branch_role)
    db_session.add(branch_role)
    await db_session.commit()

    response = await _lookup_by_phone(
        client, issue_token(creator), "3334445556", **{"X-Branch-ID": str(branch.id)}
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


async def test_lookup_by_phone_requires_invitations_create_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    response = await _lookup_by_phone(client, issue_token(viewer), "9544232271")
    assert response.status_code == 403


async def test_lookup_by_phone_id_proof_url_gated_on_documents_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    db_session.add(
        _build_invitation(
            db_session,
            branch.id,
            primary_contact_phone="7778889990",
            primary_contact_id_proof_storage_key="docs/id.jpg",
            primary_contact_photo_storage_key="docs/photo.jpg",
        )
    )
    await db_session.commit()

    plain = await _branch_scoped_invitation_creator(db_session, tenant, branch.id)
    data = (await _lookup_by_phone(client, issue_token(plain), "7778889990")).json()["data"]
    assert data["photoUrl"] is not None
    assert data["idProofUrl"] is None

    with_docs = await _branch_scoped_invitation_creator_with_documents(
        db_session, tenant, branch.id
    )
    data = (await _lookup_by_phone(client, issue_token(with_docs), "7778889990")).json()["data"]
    assert data["idProofUrl"] is not None
