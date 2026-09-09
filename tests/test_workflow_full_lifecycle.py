"""The "fully packed" end-to-end lifecycle scenario
(openspec/changes/codebase-review-and-e2e-scenario-test).

`test_workflow_staff_admin.py` and `test_workflow_visitor.py` each cover a
narrow slice of a real journey. This file composes what neither of them
does in one chain, each step feeding the next step's real response forward
(never a hardcoded id/token): platform tenant provisioning -> admin login ->
bulk branch provisioning (`POST /branches/provision`) for Branch A ->
Branch B built manually so the tenant genuinely has two branches -> custom
role creation, listing permissions, assigning and revoking a branch-role
grant -> a staff-created invitation followed by its manual approval
(asserting the approval notification was actually enqueued, not stubbed to
a silent no-op) -> a walk-in registration against Branch B, fed real
department/purpose/duration/host ids from the `visit_info` endpoints ->
`GET /invitations` scoped per branch -> the reports rollup reflecting both
branches -> the branch-deletion guard from `harden-referential-integrity-
and-rbac-gates` exercised end-to-end (blocked while active, then
succeeding once cleaned up).

Like `test_workflow_staff_admin.py`, this needs a real, freshly provisioned
tenant schema (not the shared `client`/`tenant`/`branch` fixtures) so
`POST /branches/provision` and a genuine second branch mean something —
see that file's module docstring for why a bespoke `AsyncClient` and
`get_tenant_db` override are used instead. The small provisioning/seeding
helpers below are local copies of that file's, not a cross-import: root-
level `tests/*.py` files aren't an importable package here, and duplicating
~30 lines of test-only setup is the established convention for this
situation (see `visit_info/tests.py`'s `registration_device_raw_key`
fixture docstring for the same reasoning applied one level down, inside a
real package).
"""

import io
import json
import re
import uuid
from collections.abc import AsyncGenerator, Callable

from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from factories import UserFactory, VisitorCategoryFactory
from vmss_api.auth.models import Role, UserBranchRole
from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.security import create_access_token, decode_token, hash_password
from vmss_api.core.tenancy import get_tenant_db
from vmss_api.identity_verification import senders as otp_senders
from vmss_api.invitations import tasks
from vmss_api.main import app
from vmss_api.notifications import tasks as notifications_tasks
from vmss_api.platform.models import SuperAdmin, TenantUserIndex
from vmss_api.registrations.models import RegistrationDeviceKey


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _tenant_db_not_yet_provisioned() -> AsyncSession:
    raise AssertionError(
        "get_tenant_db was called before the full-lifecycle workflow test provisioned its "
        "tenant and rebound this override — every tenant-scoped call in this chain must "
        "happen after that point."
    )


def _bind_tenant_db_override(schema_name: str) -> Callable[[], AsyncGenerator[AsyncSession]]:
    async def _override() -> AsyncGenerator[AsyncSession]:
        async with tenant_session_scope(schema_name) as session:
            yield session

    return _override


async def _seed_first_admin(
    schema_name: str, *, tenant_id: uuid.UUID, email: str, password: str
) -> None:
    """The one non-API step in this chain — see `test_workflow_staff_admin
    .py::_seed_first_admin` for why no API path can create a brand-new
    tenant's very first user.
    """
    async with tenant_session_scope(schema_name) as tenant_db:
        admin_role = (
            await tenant_db.execute(select(Role).where(Role.name == "admin"))
        ).scalar_one()

        branch_role = UserBranchRole(id=uuid.uuid4(), role=admin_role, branch_id=None)
        first_admin = UserFactory.build(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            full_name="Seed Admin",
            branch_roles=[branch_role],
        )
        tenant_db.add(first_admin)
        await tenant_db.flush()
        tenant_db.add(TenantUserIndex(email=email, tenant_id=tenant_id, user_id=first_admin.id))
        await tenant_db.commit()


_DEFAULT_VISITOR_CATEGORY_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


async def _seed_default_visitor_category(schema_name: str) -> None:
    """invitation-multi-step-approval: `visitorCategoryId` is now required on
    `InvitationCreate` — this freshly-provisioned tenant needs a real
    category row before either invitation-creation step below can succeed,
    same "one non-API seed step" posture as `_seed_first_admin`.
    """
    async with tenant_session_scope(schema_name) as tenant_db:
        tenant_db.add(
            VisitorCategoryFactory.build(
                id=_DEFAULT_VISITOR_CATEGORY_ID,
                name="Full Lifecycle Test Category",
                code="FULL-LIFECYCLE-DEFAULT",
            )
        )
        await tenant_db.commit()


class _RecordingSender:
    """Local copy of `identity_verification/tests.py::_RecordingSender` —
    same "no cross-import between root-level `tests/*.py` files" convention
    this module's docstring already documents for its other helpers.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _extract_otp_code(body: str) -> str:
    match = re.search(r"code is (\d+)", body)
    assert match is not None, body
    return match.group(1)


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _visit_details(**catalog_ids: str) -> dict:
    """Free-text visit details, optionally paired with catalog ids
    (`purposeId`/`hostId`/`durationId`/`departmentId`) the way a real kiosk
    client would after resolving them via the `visit_info` endpoints.
    """
    details = {
        "purposeOfVisit": "Site Visit",
        "hostNameOrEmail": "seed-admin@example.com",
        "preferredVisitDate": "2026-09-01",
        "preferredVisitTime": "11:00:00",
        "expectedDuration": "30 minutes",
        "departmentToVisit": "Operations",
    }
    details.update(catalog_ids)
    return details


def _invitation_payload(
    full_name: str,
    *,
    visitor_category_id: uuid.UUID = _DEFAULT_VISITOR_CATEGORY_ID,
    **catalog_ids: str,
) -> dict:
    return {
        "registrationType": "individual",
        "visitorCategoryId": str(visitor_category_id),
        "primaryContact": {
            "fullName": full_name,
            "email": f"{full_name.lower().replace(' ', '.')}@example.com",
            "preferredContactMethod": "email",
            "idProofType": "Passport",
        },
        "visitors": [],
        "visitDetails": _visit_details(**catalog_ids),
        "carriedItems": {"items": []},
        "vehicles": [],
        "consents": {
            "termsAccepted": True,
            "dataProcessingAccepted": True,
            "safetyGuidelinesAccepted": True,
        },
    }


async def _provision_device_key(
    db_session: AsyncSession, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> str:
    """`RegistrationDeviceKey` has no admin CRUD API — it's global-schema,
    provisioned only by ops tooling (see its own docstring) — so this
    inserts directly, same as `registrations/tests.py`'s
    `registration_device_raw_key` fixture does for the shared-fixture
    workflow test.
    """
    raw_key = "full-lifecycle-device-key-" + uuid.uuid4().hex
    db_session.add(
        RegistrationDeviceKey(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            key_hash=hash_password(raw_key),
            label="Branch B Kiosk",
            is_active=True,
        )
    )
    await db_session.commit()
    return raw_key


async def _run_workflow_after_provisioning(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
    *,
    suffix: str,
    tenant_id: uuid.UUID,
    slug: str,
    schema_name: str,
) -> None:
    # --- Seed step + tenant-admin login -----------------------------------
    admin_email = f"seed-admin-{suffix}@e2e-full.example"
    admin_password = "correct-password"
    await _seed_first_admin(
        schema_name, tenant_id=tenant_id, email=admin_email, password=admin_password
    )
    await _seed_default_visitor_category(schema_name)

    admin_login = await client.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": admin_password}
    )
    assert admin_login.status_code == 200
    admin_headers = _bearer(admin_login.json()["data"]["accessToken"])

    # --- Tenant profile -----------------------------------------------------
    tenant_profile_response = await client.get("/api/v1/tenants/me", headers=admin_headers)
    assert tenant_profile_response.status_code == 200, tenant_profile_response.text
    tenant_profile = tenant_profile_response.json()["data"]
    assert tenant_profile["id"] == str(tenant_id)
    assert tenant_profile["slug"] == slug

    # --- Bulk provisioning for Branch A ------------------------------------
    provision_response = await client.post(
        "/api/v1/branches/provision",
        json={
            "name": "Branch A HQ",
            "code": f"BR-A-{suffix}",
            "buildings": [
                {
                    "name": "Tower A",
                    "code": f"TWR-A-{suffix}",
                    "floors": [
                        {
                            "name": "Ground Floor",
                            "floorNumber": 0,
                            "departments": [{"name": "Operations", "code": f"OPS-{suffix}"}],
                            "receptionDesks": [{"name": "Main Desk", "code": f"DESK-A-{suffix}"}],
                        }
                    ],
                    "securityGates": [
                        {"name": "Tower Gate", "code": f"TGATE-{suffix}", "gateType": "entry"}
                    ],
                }
            ],
            "securityGates": [
                {"name": "Perimeter Gate", "code": f"PGATE-{suffix}", "gateType": "both"}
            ],
        },
        headers=admin_headers,
    )
    assert provision_response.status_code == 201, provision_response.text
    provision_data = provision_response.json()["data"]
    branch_a_id = provision_data["branch"]["id"]
    assert provision_data["buildingsCreated"] == 1
    assert provision_data["floorsCreated"] == 1
    assert provision_data["departmentsCreated"] == 1
    assert provision_data["receptionDesksCreated"] == 1
    assert provision_data["securityGatesCreated"] == 2

    # --- Branch B, built entity-by-entity so the tenant genuinely has two
    # branches for everything below to scope across ------------------------
    branch_b_response = await client.post(
        "/api/v1/branches",
        json={"name": "Branch B Annex", "code": f"BR-B-{suffix}"},
        headers=admin_headers,
    )
    assert branch_b_response.status_code == 201
    branch_b_id = branch_b_response.json()["data"]["id"]

    building_b_response = await client.post(
        "/api/v1/buildings",
        json={"branchId": branch_b_id, "name": "Annex Building", "code": f"TWR-B-{suffix}"},
        headers=admin_headers,
    )
    assert building_b_response.status_code == 201
    building_b_id = building_b_response.json()["data"]["id"]

    department_b_response = await client.post(
        "/api/v1/departments",
        json={"branchId": branch_b_id, "name": "Front Office", "code": f"FO-{suffix}"},
        headers=admin_headers,
    )
    assert department_b_response.status_code == 201
    department_b_id = department_b_response.json()["data"]["id"]

    # --- Role management: custom role, permission catalog, assign + revoke,
    # then a standard role so Branch A has a real staff member -------------
    permissions_response = await client.get("/api/v1/auth/permissions", headers=admin_headers)
    assert permissions_response.status_code == 200
    catalog_codes = {p["code"] for p in permissions_response.json()["data"]}
    assert {"invitations:create", "invitations:view"} <= catalog_codes

    custom_role_response = await client.post(
        "/api/v1/auth/roles",
        json={
            "name": f"lobby-ambassador-{suffix}",
            "permissionCodes": ["invitations:create", "invitations:view"],
        },
        headers=admin_headers,
    )
    assert custom_role_response.status_code == 201
    custom_role_id = custom_role_response.json()["data"]["id"]

    staff_response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": f"staff-{suffix}@e2e-full.example",
            "password": "correct-password",
            "fullName": "Branch A Staff",
        },
        headers=admin_headers,
    )
    assert staff_response.status_code == 201
    staff_user_id = staff_response.json()["data"]["id"]

    grant_response = await client.post(
        f"/api/v1/auth/users/{staff_user_id}/branch-roles",
        json={"roleId": custom_role_id, "branchId": branch_a_id},
        headers=admin_headers,
    )
    assert grant_response.status_code == 201
    grant_assignment_id = grant_response.json()["data"]["id"]

    revoke_response = await client.delete(
        f"/api/v1/auth/users/{staff_user_id}/branch-roles/{grant_assignment_id}",
        headers=admin_headers,
    )
    assert revoke_response.status_code == 204

    roles_response = await client.get("/api/v1/auth/roles", headers=admin_headers)
    assert roles_response.status_code == 200
    reception_role_id = next(
        r["id"] for r in roles_response.json()["data"] if r["name"] == "reception"
    )
    re_grant_response = await client.post(
        f"/api/v1/auth/users/{staff_user_id}/branch-roles",
        json={"roleId": reception_role_id, "branchId": branch_a_id},
        headers=admin_headers,
    )
    assert re_grant_response.status_code == 201

    # --- Visitor categories: a category and its approval workflow rule -----
    visitor_category_response = await client.post(
        "/api/v1/visitor-categories",
        json={
            "name": f"Interview Candidate {suffix}",
            "code": f"INTERVIEW-{suffix}",
            "description": "Job applicants",
            "formSchema": [
                {
                    "name": "position_applied",
                    "label": "Position Applied For",
                    "fieldType": "text",
                    "required": True,
                }
            ],
        },
        headers=admin_headers,
    )
    assert visitor_category_response.status_code == 201, visitor_category_response.text
    visitor_category_id = visitor_category_response.json()["data"]["id"]

    approval_workflow_rule_response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": visitor_category_id,
            "stepOrder": 1,
            "approverRoleId": reception_role_id,
        },
        headers=admin_headers,
    )
    assert approval_workflow_rule_response.status_code == 201, approval_workflow_rule_response.text
    approval_workflow_rule = approval_workflow_rule_response.json()["data"]
    assert approval_workflow_rule["visitorCategoryId"] == visitor_category_id

    # --- Staff-created invitation at Branch A, then manual approval --------
    approval_calls: list[dict] = []

    def _record_approval(**kwargs) -> None:
        approval_calls.append(kwargs)

    tracking_calls: list[dict] = []

    def _record_tracking(**kwargs) -> None:
        tracking_calls.append(kwargs)

    original_approval_delay = tasks.send_approval_notification.delay
    original_tracking_delay = tasks.send_tracking_notification.delay
    tasks.send_approval_notification.delay = _record_approval
    tasks.send_tracking_notification.delay = _record_tracking
    try:
        create_invitation_response = await client.post(
            "/api/v1/invitations",
            data={"payload": json.dumps(_invitation_payload("Priya Nair"))},
            files=[
                ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
                ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            ],
            headers={**admin_headers, "X-Branch-ID": branch_a_id},
        )
        assert create_invitation_response.status_code == 201, create_invitation_response.text
        invitation_a = create_invitation_response.json()["data"]
        assert invitation_a["status"] == "submitted"
        assert len(tracking_calls) == 1

        # role-based-invitation-workflow: every submitted invitation now
        # gets an unconditional stepOrder-0 ownership step (role-identified
        # for the tenant's default host role), so the blanket
        # `POST /invitations/{id}/approve` endpoint always 409s now —
        # approval goes through the step endpoint instead, same as any
        # other workflow-backed invitation.
        assert invitation_a["currentApprovalStep"] is not None
        current_step_id = invitation_a["currentApprovalStep"]["id"]
        approve_response = await client.post(
            f"/api/v1/invitations/{invitation_a['id']}/approval-steps/{current_step_id}/approve",
            headers=admin_headers,
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["data"]["status"] == "approved"
        assert len(approval_calls) == 1
        assert approval_calls[0]["invitation_id"] == invitation_a["id"]

        # --- Delegation + relevantToMe (invitation-relevant-to-me-and-
        # delegation): a host-and-role-chain invitation under the
        # "Interview Candidate" category's workflow rule, the host
        # delegating the role-identified step following their own to the
        # Branch A staff member who already holds that role, and the
        # delegate — not just any holder of the role — acting on it via
        # their personal `relevantToMe` worklist. Push notifications are
        # captured the same monkeypatch-`.delay` way as the email/SMS tasks
        # above, confirming both channels still fire correctly together and
        # that delegation itself triggers no notification of its own
        # (approvals/service.py::delegate_step sends none — see this
        # change's design.md Decision 3). ---------------------------------
        push_calls: list[dict] = []

        def _record_push(**kwargs) -> None:
            push_calls.append(kwargs)

        original_push_delay = notifications_tasks.send_push.delay
        notifications_tasks.send_push.delay = _record_push
        try:
            admin_user_id = decode_token(admin_headers["Authorization"].removeprefix("Bearer "))[
                "sub"
            ]

            # role-based-invitation-workflow: `hostId` is no longer accepted
            # at creation — every submitted invitation's ownership step
            # (stepOrder 0) starts role-identified for the tenant's default
            # host role (reception), not host-identified. The admin (who
            # already holds every reception permission via override) first
            # delegates that step to themselves as the real host, then the
            # scenario continues exactly as before.
            create_delegatable_response = await client.post(
                "/api/v1/invitations",
                data={
                    "payload": json.dumps(
                        _invitation_payload(
                            "Dana Delegate Host",
                            visitor_category_id=uuid.UUID(visitor_category_id),
                        )
                    )
                },
                files=[
                    ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
                    ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
                ],
                headers={**admin_headers, "X-Branch-ID": branch_a_id},
            )
            assert create_delegatable_response.status_code == 201, create_delegatable_response.text
            delegatable_invitation = create_delegatable_response.json()["data"]
            assert delegatable_invitation["status"] == "submitted"
            assert delegatable_invitation["hostId"] is None
            # Submission's ownership step (stepOrder 0) is current — one
            # push to every holder of the tenant's default host role at the
            # branch (specs/invitations/spec.md "Submission Notifies the
            # Owning Role via Push").
            assert len(push_calls) == 1

            invitation_detail_response = await client.get(
                f"/api/v1/invitations/{delegatable_invitation['id']}", headers=admin_headers
            )
            assert invitation_detail_response.status_code == 200
            ownership_step_id = invitation_detail_response.json()["data"]["currentApprovalStep"][
                "id"
            ]

            delegate_host_response = await client.post(
                f"/api/v1/invitations/{delegatable_invitation['id']}/approval-steps/"
                f"{ownership_step_id}/delegate",
                json={"delegateUserId": admin_user_id},
                headers=admin_headers,
            )
            assert delegate_host_response.status_code == 200, delegate_host_response.text
            assert delegate_host_response.json()["data"]["hostId"] == admin_user_id
            # Delegating the ownership step resolves the invitation's host
            # and notifies them (approvals capability's "Delegating the
            # Ownership Step Also Resolves the Invitation's Host") — a
            # second push.
            assert len(push_calls) == 2

            approve_host_step_response = await client.post(
                f"/api/v1/invitations/{delegatable_invitation['id']}/approval-steps/"
                f"{ownership_step_id}/approve",
                headers=admin_headers,
            )
            assert approve_host_step_response.status_code == 200, approve_host_step_response.text
            role_step = approve_host_step_response.json()["data"]["currentApprovalStep"]
            assert role_step is not None
            assert role_step["approverRoleId"] == reception_role_id
            assert role_step["delegatedToUserId"] is None
            role_step_id = role_step["id"]
            # The role-identified step becoming current broadcasts a third
            # push to every reception-role holder at Branch A, including
            # `staff_user_id` below (approvals/service.py::_activate_next_step).
            assert len(push_calls) == 3

            delegate_response = await client.post(
                f"/api/v1/invitations/{delegatable_invitation['id']}/approval-steps/"
                f"{role_step_id}/delegate",
                json={"delegateUserId": staff_user_id},
                headers=admin_headers,
            )
            assert delegate_response.status_code == 200, delegate_response.text
            delegated_step = delegate_response.json()["data"]["currentApprovalStep"]
            assert delegated_step["delegatedToUserId"] == staff_user_id
            # Delegating a later (non-ownership) step sends no notification
            # of its own and does not change the already-resolved host —
            # the delegate, by construction, already held the role at
            # Branch A and so was already in the broadcast set above.
            assert len(push_calls) == 3

            delegate_token = create_access_token(uuid.UUID(staff_user_id), tenant_id)
            relevant_to_me_response = await client.get(
                "/api/v1/invitations",
                params={"relevantToMe": "true"},
                headers=_bearer(delegate_token),
            )
            assert relevant_to_me_response.status_code == 200, relevant_to_me_response.text
            relevant_tracking_ids = {
                i["trackingId"] for i in relevant_to_me_response.json()["data"]
            }
            assert delegatable_invitation["trackingId"] in relevant_tracking_ids

            delegate_approve_response = await client.post(
                f"/api/v1/invitations/{delegatable_invitation['id']}/approval-steps/"
                f"{role_step_id}/approve",
                headers=_bearer(delegate_token),
            )
            assert delegate_approve_response.status_code == 200, delegate_approve_response.text
            assert delegate_approve_response.json()["data"]["status"] == "approved"
            # The role step was the workflow's last one — finalizing the
            # invitation dispatches the same visitor-facing approval
            # notification as `invitation_a`'s direct approval above
            # (`approval_calls`), plus a fourth push telling the resolved
            # host their invitation was approved (`invitations/service.py::
            # approve_invitation`'s own `notify_user` call — unrelated to
            # delegation itself, no further push fires for the step chain
            # since there is no next step to activate).
            assert len(approval_calls) == 2
            assert len(push_calls) == 4
            assert push_calls[3]["title"] == "Invitation approved"
        finally:
            notifications_tasks.send_push.delay = original_push_delay

        # --- Audit trail: the delegation action performed above is
        # retrievable through its own history-tracking API, closing the
        # write (`record_audit_log`, a `BackgroundTasks` job on the
        # `delegate_step` call above) / read loop
        # (verify-audit-trail-and-delegation-full-suite/design.md
        # Decision 2 — a same-purpose spot-check here, in addition to the
        # dedicated `audit_trail/tests.py` integration test). --------------
        audit_trail_response = await client.get(
            "/api/v1/audit-trail",
            params={"entityId": role_step_id, "action": "invitation_approval_step_delegated"},
            headers=admin_headers,
        )
        assert audit_trail_response.status_code == 200, audit_trail_response.text
        audit_entries = audit_trail_response.json()["data"]
        assert len(audit_entries) == 1
        audit_entry = audit_entries[0]
        assert audit_entry["entityType"] == "InvitationApprovalStep"
        assert audit_entry["entityId"] == role_step_id
        assert audit_entry["actorUserId"] == admin_user_id

        audit_detail_response = await client.get(
            f"/api/v1/audit-trail/{audit_entry['id']}", headers=admin_headers
        )
        assert audit_detail_response.status_code == 200, audit_detail_response.text
        assert audit_detail_response.json()["data"]["diff"] == {"delegatedToUserId": staff_user_id}

        # --- Walk-in registration at Branch B, fed real visit_info lookups -
        device_key = await _provision_device_key(
            db_session, tenant_id=tenant_id, branch_id=uuid.UUID(branch_b_id)
        )
        device_headers = {"X-Device-Key": device_key}

        departments_response = await client.get(
            "/api/v1/visit-info/departments", headers=device_headers
        )
        assert departments_response.status_code == 200, departments_response.text
        looked_up_departments = departments_response.json()["data"]["departments"]
        assert [d["id"] for d in looked_up_departments] == [department_b_id]

        options_response = await client.get("/api/v1/visit-info/options", headers=device_headers)
        assert options_response.status_code == 200, options_response.text
        options_data = options_response.json()["data"]
        assert options_data["purposes"], "expected the real tenant migration to seed purposes"
        assert options_data["durations"], "expected the real tenant migration to seed durations"
        purpose_id = options_data["purposes"][0]["id"]
        duration_id = options_data["durations"][0]["id"]

        hosts_response = await client.get("/api/v1/hosts/search", headers=device_headers)
        assert hosts_response.status_code == 200, hosts_response.text
        hosts = hosts_response.json()["data"]["hosts"]
        assert hosts, "expected the seed admin to appear as a browsable host"
        host_id = hosts[0]["id"]

        # --- OTP verification for the walk-in visitor's own contact ---------
        # Proves the standalone identity-verification endpoints work inside
        # this same session; the returned proof token isn't wired into the
        # walk-in payload below — nothing in the API consumes it yet (see
        # design.md's Non-Goals).
        walk_in_email = "walk.in.visitor@example.com"
        # `identity-verification`'s public endpoints resolve
        # `settings.default_tenant_slug` (no bearer token/tenant identifier
        # of their own) rather than this test's freshly platform-provisioned
        # tenant — point it at this tenant's own slug for the duration of
        # this call, the same fixture pattern
        # `identity_verification/tests.py`'s own tests use.
        monkeypatch.setattr(settings, "default_tenant_slug", slug)
        otp_recorder = _RecordingSender()
        original_email_sender = otp_senders.email_sender
        otp_senders.email_sender = otp_recorder
        try:
            otp_request_response = await client.post(
                "/api/v1/identity-verification/otp/request",
                json={"identifier": walk_in_email, "channel": "email"},
            )
            assert otp_request_response.status_code == 200, otp_request_response.text
            assert len(otp_recorder.calls) == 1
            otp_code = _extract_otp_code(otp_recorder.calls[0]["body"])

            otp_verify_response = await client.post(
                "/api/v1/identity-verification/otp/verify",
                json={"identifier": walk_in_email, "channel": "email", "code": otp_code},
            )
            assert otp_verify_response.status_code == 200, otp_verify_response.text
            proof_token = otp_verify_response.json()["data"]["proofToken"]
            proof_claims = decode_token(proof_token)
            assert proof_claims["sub"] == walk_in_email
            assert proof_claims["type"] == "identity_verified"
            assert proof_claims["channel"] == "email"
        finally:
            otp_senders.email_sender = original_email_sender

        walk_in_response = await client.post(
            "/api/v1/registrations/walk-in",
            data={
                "payload": json.dumps(
                    _invitation_payload(
                        "Walk In Visitor",
                        departmentId=department_b_id,
                        purposeId=purpose_id,
                        durationId=duration_id,
                        hostId=host_id,
                    )
                )
            },
            files=[
                ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
                ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
            ],
            headers=device_headers,
        )
        assert walk_in_response.status_code == 201, walk_in_response.text
        walk_in_data = walk_in_response.json()["data"]
        assert walk_in_data["status"] == "submitted"
    finally:
        tasks.send_approval_notification.delay = original_approval_delay
        tasks.send_tracking_notification.delay = original_tracking_delay

    # --- Branch-scoped invitation listing -----------------------------------
    branch_a_invitations = await client.get(
        "/api/v1/invitations", headers={**admin_headers, "X-Branch-ID": branch_a_id}
    )
    assert branch_a_invitations.status_code == 200
    branch_a_tracking_ids = {i["trackingId"] for i in branch_a_invitations.json()["data"]}
    assert invitation_a["trackingId"] in branch_a_tracking_ids
    assert walk_in_data["trackingId"] not in branch_a_tracking_ids

    branch_b_invitations = await client.get(
        "/api/v1/invitations", headers={**admin_headers, "X-Branch-ID": branch_b_id}
    )
    assert branch_b_invitations.status_code == 200
    branch_b_tracking_ids = {i["trackingId"] for i in branch_b_invitations.json()["data"]}
    assert walk_in_data["trackingId"] in branch_b_tracking_ids
    assert invitation_a["trackingId"] not in branch_b_tracking_ids

    # --- Reports rollup reflecting both branches ----------------------------
    rollup_response = await client.get("/api/v1/reports/branches/rollup", headers=admin_headers)
    assert rollup_response.status_code == 200
    rollup = rollup_response.json()["data"]
    assert rollup["totalBranches"] == 2
    assert rollup["totalSecurityGates"] == 2

    branch_a_rollup = next(b for b in rollup["branches"] if b["branchId"] == branch_a_id)
    assert branch_a_rollup["buildingCount"] == 1
    assert branch_a_rollup["floorCount"] == 1
    assert branch_a_rollup["departmentCount"] == 1
    assert branch_a_rollup["receptionDeskCount"] == 1
    assert branch_a_rollup["securityGateCount"] == 2

    branch_b_rollup = next(b for b in rollup["branches"] if b["branchId"] == branch_b_id)
    assert branch_b_rollup["buildingCount"] == 1
    assert branch_b_rollup["floorCount"] == 0
    assert branch_b_rollup["departmentCount"] == 1
    assert branch_b_rollup["receptionDeskCount"] == 0
    assert branch_b_rollup["securityGateCount"] == 0

    # --- Branch-deletion guard, exercised end-to-end ------------------------
    # (harden-referential-integrity-and-rbac-gates): Branch B still has an
    # active building, department, and device key, so deleting it is
    # rejected — the exact fix for the originally reported bug.
    blocked_delete_response = await client.delete(
        f"/api/v1/branches/{branch_b_id}", headers=admin_headers
    )
    assert blocked_delete_response.status_code == 409

    delete_building_response = await client.delete(
        f"/api/v1/buildings/{building_b_id}", headers=admin_headers
    )
    assert delete_building_response.status_code == 204

    delete_department_response = await client.delete(
        f"/api/v1/departments/{department_b_id}", headers=admin_headers
    )
    assert delete_department_response.status_code == 204

    await db_session.execute(
        update(RegistrationDeviceKey)
        .where(RegistrationDeviceKey.branch_id == uuid.UUID(branch_b_id))
        .values(is_active=False)
    )
    await db_session.commit()

    # Branch B's code (`BR-B-{suffix}`) must never collide with the
    # walk-in no-device-key fallback's configured default branch code, or
    # this deletion would also be rejected by
    # `protect-walkin-default-branch-config`'s guard — a test-data
    # coincidence, not something this workflow is testing. Asserted
    # explicitly so a future change to either value can't silently
    # reintroduce the collision `conftest.py`'s shared `branch` fixture
    # already had with it.
    assert f"BR-B-{suffix}" != settings.registration_default_branch_code

    final_delete_response = await client.delete(
        f"/api/v1/branches/{branch_b_id}", headers=admin_headers
    )
    assert final_delete_response.status_code == 204


async def test_full_lifecycle_workflow(
    superadmin: SuperAdmin, db_session: AsyncSession, monkeypatch
) -> None:
    async def _override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_tenant_db] = _tenant_db_not_yet_provisioned
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            platform_login = await client.post(
                "/api/v1/platform/auth/login",
                json={"email": superadmin.email, "password": "correct-password"},
            )
            assert platform_login.status_code == 200
            platform_token = platform_login.json()["data"]["accessToken"]

            suffix = uuid.uuid4().hex[:8]
            slug = f"e2e-full-{suffix}"
            create_tenant_response = await client.post(
                "/api/v1/platform/tenants",
                json={"name": "E2E Full Lifecycle Co", "slug": slug},
                headers=_bearer(platform_token),
            )
            assert create_tenant_response.status_code == 201
            tenant_data = create_tenant_response.json()["data"]
            tenant_id = uuid.UUID(tenant_data["id"])
            schema_name = f"{settings.tenant_schema_prefix}{slug}"

            app.dependency_overrides[get_tenant_db] = _bind_tenant_db_override(schema_name)

            try:
                await _run_workflow_after_provisioning(
                    client,
                    db_session,
                    monkeypatch,
                    suffix=suffix,
                    tenant_id=tenant_id,
                    slug=slug,
                    schema_name=schema_name,
                )
            finally:
                # Same reasoning as `test_workflow_staff_admin.py`'s
                # "Deviation from design.md" note: leaving this schema
                # behind breaks every later test's `db_session` teardown via
                # a `role_permissions` -> `global.permissions` FK.
                await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                await db_session.execute(
                    update(RegistrationDeviceKey)
                    .where(RegistrationDeviceKey.tenant_id == tenant_id)
                    .values(is_active=False)
                )
                await db_session.commit()
    finally:
        app.dependency_overrides.clear()
