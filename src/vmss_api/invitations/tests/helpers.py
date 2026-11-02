"""Shared builders, fakes and constants for the invitation tests.

None
"""

import asyncio
import csv
import html as html_lib
import io
import json
import re
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any

from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    InvitationApprovalStepFactory,
    InvitationFactory,
    InvitationVisitorFactory,
    PermissionFactory,
    RoleFactory,
    UserFactory,
    with_default_location,
)
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import AuditLog, Permission, User, UserBranchRole
from vmss_api.auth.repository import RoleRepository
from vmss_api.core.security import hash_password
from vmss_api.form_builder.defaults import _stable_id as _form_builder_stable_id
from vmss_api.invitations import export as invitation_export
from vmss_api.invitations import notifications, tasks
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVisitor,
)
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.invitations.repository import InvitationExportNames
from vmss_api.invitations.schemas import (
    ExportFormat,
    InvitationExportDateRange,
)
from vmss_api.notifications import service as notifications_service
from vmss_api.org_structure.models import Branch, Company
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant

# Fixed id baked into `_individual_payload()`/`_group_payload()` below, and
# created for real by the `_default_visitor_category` autouse fixture — every
# test in this module gets a valid, active `visitorCategoryId` for free
# without having to plumb one through each of the ~40 call sites that build
# an invitation-creation payload.
_DEFAULT_VISITOR_CATEGORY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


_DEFAULT_CONSENT_KEYS = (
    "terms_accepted",
    "data_processing_accepted",
    "safety_guidelines_accepted",
)


# Set by any of the admin-side `_create_and_publish_*`/`_configure_and_
# publish_branch_field`/`_update_and_publish_group_range` helpers below,
# reset to `None` before every test by `_reset_live_consent_field_ids`
# (autouse). Publishing seeds the branch's default steps/fields as *real*
# database rows (random ids) the first time anything is fetched/published
# for it — a branch that's never touched form-builder admin endpoints at
# all still resolves against `DEFAULT_EFFECTIVE_FORM`'s deterministic
# ids (`_default_consent_field_id` below), but the moment a test publishes
# anything, the branch's Consent Agreement fields get real ids that no
# longer match that deterministic fallback (restructure-walkin-payload-
# by-field-id). This lets `_individual_payload()`/`_group_payload()` keep
# working unmodified either way, without every publishing test having to
# separately re-derive and patch its own `consents`.
_live_consent_field_ids: dict[str, str] | None = None


def _record_live_consent_field_ids(steps: list[dict]) -> None:
    """Called by every admin-side setup helper right after it publishes, so
    subsequent `_individual_payload()`/`_group_payload()` calls in the same
    test pick up the branch's now-real Consent Agreement field ids."""
    global _live_consent_field_ids
    step = next((s for s in steps if s["key"] == "consent_agreement"), None)
    if step is None:
        return
    _live_consent_field_ids = {f["key"]: f["id"] for f in step["fields"]}


def _default_consent_field_id(key: str) -> str:
    """The current Consent Agreement field id for `key` — the branch's own
    real id if a test has published anything for it
    (`_live_consent_field_ids`), otherwise the deterministic id
    `form_builder/defaults.py::DEFAULT_EFFECTIVE_FORM` assigns it, matching
    what `resolve_effective_form` falls back to for a branch with no
    published `FormConfigVersion` at all (restructure-walkin-payload-by-
    field-id). Lets `_individual_payload()`/`_group_payload()` submit
    `consents` by id without every test needing its own form-builder round
    trip.
    """
    if _live_consent_field_ids is not None and key in _live_consent_field_ids:
        return _live_consent_field_ids[key]
    return str(_form_builder_stable_id("field", "consent_agreement", key))


def _set_consent_accepted(payload: dict, key: str, accepted: bool) -> None:
    """Mutates `payload["consents"]` (built by `_individual_payload()`/
    `_group_payload()`) in place, flipping the default consent field
    identified by its default *key* to `accepted` — a test-authoring
    convenience so call sites can keep referring to a consent by its
    readable default key instead of `_default_consent_field_id(key)`."""
    field_id = _default_consent_field_id(key)
    entry = next(c for c in payload["consents"] if c["fieldId"] == field_id)
    entry["accepted"] = accepted


def _add_consent(payload: dict, field_id: str, accepted: bool) -> None:
    payload["consents"].append({"fieldId": field_id, "accepted": accepted})


def _remove_default_consent(payload: dict, key: str) -> None:
    """Drops the default consent field identified by its default *key*
    from `payload["consents"]` in place."""
    field_id = _default_consent_field_id(key)
    payload["consents"] = [c for c in payload["consents"] if c["fieldId"] != field_id]


def _custom_field_value(entries: list[dict], field_id: str) -> Any:
    """Looks up one `{fieldId, value}` entry's `value` out of a response's
    `customFields` array by `fieldId` — the
    read-side counterpart of building a `customFields` request array by
    hand (restructure-walkin-payload-by-field-id)."""
    return next(e["value"] for e in entries if e["fieldId"] == field_id)


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _individual_payload() -> dict:
    return {
        "registrationType": "individual",
        "visitorCategoryId": str(_DEFAULT_VISITOR_CATEGORY_ID),
        "primaryContact": {
            "fullName": "Meera Krishnan",
            "email": "meera.krishnan@example.com",
            "preferredContactMethod": "email",
            "idProofType": "Passport",
        },
        "visitors": [],
        "visitDetails": {
            "purposeOfVisit": "Interview",
            "hostNameOrEmail": "hr@enterprise-ugo.co",
            "preferredVisitDate": "2026-08-12",
            "preferredVisitTime": "10:00:00",
            "expectedDuration": "< 1 hour",
            "departmentToVisit": "Human Resources",
        },
        "carriedItems": {"items": []},
        "vehicles": [],
        # Referenced by fieldId, never key/label
        # (restructure-walkin-payload-by-field-id) — one entry per default
        # Consent Agreement field, for a branch that has never customized it.
        "consents": [
            {"fieldId": _default_consent_field_id("terms_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("data_processing_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("safety_guidelines_accepted"), "accepted": True},
        ],
    }


def _group_payload() -> dict:
    return {
        "registrationType": "group",
        "visitorCategoryId": str(_DEFAULT_VISITOR_CATEGORY_ID),
        "primaryContact": {
            "fullName": "Priya Sharma",
            "email": "priya.sharma@enterprise-ugo.co",
            "phone": "+91 98765 43210",
            "preferredContactMethod": "email",
            "idProofType": "Aadhaar Card",
        },
        "visitors": [
            {
                "fullName": "Alexander Pierce",
                "email": "alexander.p@enterprise-ugo.co",
                "idProofType": "Aadhaar Card",
            },
            {
                "fullName": "Clara Oswald",
                "phone": "+1 (555) 014-0362",
                "idProofType": "Passport",
            },
        ],
        "visitDetails": {
            "purposeOfVisit": "Business Meeting",
            "hostNameOrEmail": "Rahul Nair",
            "preferredVisitDate": "2026-08-15",
            "preferredVisitTime": "14:30:00",
            "expectedDuration": "1-2 hours",
            "departmentToVisit": "Engineering",
        },
        "carriedItems": {
            "items": ["laptop_tablet", "mobile_phone"],
            "itemDescription": "2 laptops",
        },
        "vehicles": [
            {
                "vehicleType": "4_wheeler",
                "licensePlate": "KA-01-AB-1234",
                "makeModel": "Honda City",
                "color": "White",
            },
            {"vehicleType": "2_wheeler", "licensePlate": "KA-05-CD-5678"},
        ],
        "consents": [
            {"fieldId": _default_consent_field_id("terms_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("data_processing_accepted"), "accepted": True},
            {"fieldId": _default_consent_field_id("safety_guidelines_accepted"), "accepted": True},
        ],
    }


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


def _answers(values: object) -> object:
    """Detail answers now also carry the field's display `fieldName`/
    `fieldKey` (and a group's `groupName`). Assertions written against the
    `{fieldId, value}` wire shape compare on that projection."""
    if isinstance(values, list):
        return [_answers(v) for v in values]
    if isinstance(values, dict):
        labels = {"fieldName", "fieldKey", "groupName"}
        return {k: _answers(v) for k, v in values.items() if k not in labels}
    return values


async def _create_invitation(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    payload: dict,
    visitor_file_count: int = 0,
    idempotency_key: str | None = None,
) -> Response:
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    payload = await with_default_location(payload, branch.id)
    files = [
        ("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")),
        ("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    files += [
        ("visitor_id_proof_files", (f"v{i}.jpg", _jpeg_bytes(), "image/jpeg"))
        for i in range(visitor_file_count)
    ]
    return await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=headers,
    )


async def _create_invitation_success(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    payload: dict,
    visitor_file_count: int = 0,
    idempotency_key: str | None = None,
) -> dict:
    response = await _create_invitation(
        client,
        token,
        branch,
        payload=payload,
        visitor_file_count=visitor_file_count,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _update_and_publish_group_range(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    group_key: str,
    min_instances: int | None = None,
    max_instances: int | None = None,
) -> dict:
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)
    group = next(g for g in step["groups"] if g["key"] == group_key)

    body: dict[str, Any] = {}
    if min_instances is not None:
        body["minInstances"] = min_instances
    if max_instances is not None:
        body["maxInstances"] = max_instances
    update_response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}", json=body, headers=headers
    )
    assert update_response.status_code == 200, update_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    return update_response.json()["data"]


async def _create_and_publish_custom_group(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    group_key: str,
    field_key: str,
    min_instances: int | None = None,
    max_instances: int | None = None,
    field_type: str = "text",
    is_required: bool = False,
    options: list[str] | None = None,
    visibility_condition: dict[str, Any] | None = None,
) -> dict:
    """Admin-side setup: creates a repeatable field group with one field on
    `step_key` and publishes the branch's scope so `create_invitation`
    reads it. `visibility_condition`, if supplied, is applied to the group
    itself after creation (add-repeatable-field-groups) — its `fieldKey`
    must reference an existing field on the same step other than this
    group's own.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)

    group_body: dict[str, Any] = {"key": group_key, "name": group_key.title(), "isRepeatable": True}
    if min_instances is not None:
        group_body["minInstances"] = min_instances
    if max_instances is not None:
        group_body["maxInstances"] = max_instances
    group_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups", json=group_body, headers=headers
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()["data"]

    field_body: dict[str, Any] = {
        "key": field_key,
        "label": field_key.replace("_", " ").title(),
        "fieldType": field_type,
        "isRequired": is_required,
        "groupId": group["id"],
    }
    if options is not None:
        field_body["options"] = options
    field_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=field_body, headers=headers
    )
    assert field_response.status_code == 201, field_response.text
    # Test-only, not a real API response field (restructure-walkin-payload-
    # by-field-id) — every group this helper builds has exactly one field,
    # so `_group_entry` below can look its id up here rather than every
    # call site threading it through separately.
    field_id = field_response.json()["data"]["id"]

    if visibility_condition is not None:
        condition_response = await client.patch(
            f"/api/v1/form-builder/groups/{group['id']}",
            json={"visibilityCondition": visibility_condition},
            headers=headers,
        )
        assert condition_response.status_code == 200, condition_response.text
        group = condition_response.json()["data"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    group["_field_id"] = field_id
    return group


def _group_entry(group: dict, instances: list[dict[str, Any]]) -> dict:
    """Builds one `payload["groups"]` entry from a `_create_and_publish_
    custom_group` group dict and a list of `{fieldKey: value}` instance
    dicts (test-authoring convenience, since every group this test module
    builds has exactly one field) — converts each instance to the
    `{fieldId, value}` array shape (restructure-walkin-payload-by-field-id).
    """
    field_id = group["_field_id"]
    return {
        "groupId": group["id"],
        "instances": [
            [{"fieldId": field_id, "value": v} for v in instance.values()] for instance in instances
        ],
    }


async def _create_and_publish_additional_visitors_group(
    client: AsyncClient, headers: dict[str, str], *, id_upload_required: bool
) -> dict:
    """Admin-side setup shared by the `groupFieldFiles` tests below: a
    repeatable "Additional Visitors" group on Visitor Info with a required
    `name` field and its own `file_upload`-typed field (`id_upload`).
    Returns the group dict augmented with `_field_ids` (a `{key: id}` map
    — restructure-walkin-payload-by-field-id) so callers can build
    `payload.groups`/`groupFieldFiles[<groupId>]` without a second lookup.
    """
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == "visitor_info")

    group_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "additional_visitors", "name": "Additional Visitors", "isRepeatable": True},
        headers=headers,
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()["data"]

    field_ids: dict[str, str] = {}
    for field_key, field_type, is_required in (
        ("name", "text", True),
        ("id_upload", "file_upload", id_upload_required),
    ):
        field_response = await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": field_key,
                "label": field_key.replace("_", " ").title(),
                "fieldType": field_type,
                "isRequired": is_required,
                "groupId": group["id"],
            },
            headers=headers,
        )
        assert field_response.status_code == 201, field_response.text
        field_ids[field_key] = field_response.json()["data"]["id"]

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    group["_field_ids"] = field_ids
    return group


def _phone_only_primary_contact(payload: dict, *, full_name: str, phone: str) -> dict:
    """Swaps `payload["primaryContact"]` to a phone-only contact (no email)
    — `preferredContactMethod` must be `sms` in that case, per
    `InvitationPrimaryContactCreate._check_contact`.
    """
    payload["primaryContact"] = {
        "fullName": full_name,
        "phone": phone,
        "preferredContactMethod": "sms",
        "idProofType": "Passport",
    }
    return payload


async def _branch_scoped_invitation_viewer(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A branch-wide invitation viewer (`invitations:view` +
    `invitations:view-all`) at `branch_id` — the branch-scoping counterpart
    of `org_structure/tests.py`'s `_branch_scoped_user`, applied to this
    feature's own permissions. See `_branch_scoped_host` for a caller holding
    `invitations:view` alone (restrict-delegated-invitation-visibility).
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in ("invitations:view", "invitations:view-all")
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-viewer", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Viewer",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_editor(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A caller whose only role grant is `invitations:edit` at `branch_id` —
    holds enough to reach `PATCH /invitations/{id}/edit` at all, but not
    `invitations:approve`, for point-of-contact authorization tests
    (add-invitation-point-of-contact: setting `pocUserId`/`pocRoleId`
    requires `invitations:approve` in addition to this endpoint's own
    `invitations:edit` gate).
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:edit", description="invitations:edit"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-editor", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"editor-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Editor",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_and_documents_viewer(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """Same as `_branch_scoped_invitation_viewer` but additionally holds
    `documents:view` at `branch_id` —
    enrich-invitation-checkin-and-detail-views spec.md "Primary Contact and
    Visitor ID-Proof Documents Are Surfaced Only to Callers Holding
    documents:view".
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in ("invitations:view", "invitations:view-all", "documents:view")
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name="documents-viewer", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"docs-viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Documents Viewer",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_creator(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A caller whose only role grant is `invitations:create` at
    `branch_id` — same shape as `_branch_scoped_invitation_viewer`, for
    `GET /invitations/lookup-by-email`'s branch-scoped
    `require_branch_scope("invitations:create")` gate
    (add-invitation-lookup-by-email/design.md).
    """
    permission = await _get_or_create_permission(db_session, "invitations:create")
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-creator", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"creator-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Creator",
        branch_roles=[branch_role],
    )
    db_session.add_all([role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_invitation_creator_with_documents(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """Same as `_branch_scoped_invitation_creator` but additionally holds
    `documents:view` at `branch_id` — for
    `GET /invitations/lookup-by-email`'s `idProofUrl` gating (spec.md
    "ID-proof URL Is Resolved With documents:view").
    """
    permissions = [
        await _get_or_create_permission(db_session, code)
        for code in ("invitations:create", "documents:view")
    ]
    role = RoleFactory.build(
        id=uuid.uuid4(), name="creator-with-documents", permissions=permissions
    )
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"creator-docs-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Creator With Documents",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


def _build_invitation(
    db_session: AsyncSession,
    branch_id: uuid.UUID,
    **overrides,
):
    """Builds (but does not add/commit) an `Invitation` row via the shared
    `InvitationFactory` (testing-standards.md §1) rather than a hand-built
    dict — callers add and commit once, per query-performance.md §3's
    "commit once, not once per row" habit, applied here to test setup.
    `created_by_user_id` is forced to `None`: it's a real FK to `users`, and
    polyfactory's auto-generated UUID for it never matches an actual row.
    `registration_type`/`source` default to a valid enum value each, since
    the router maps the plain string columns back through
    `RegistrationType`/`RegistrationSource` when serializing a list row.
    """
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    return InvitationFactory.build(id=uuid.uuid4(), branch_id=branch_id, **overrides)


async def _submitted_with_steps(
    db_session: AsyncSession, branch_id: uuid.UUID, approver: User, *, pending_from: int
) -> Invitation:
    invitation = _build_invitation(
        db_session,
        branch_id,
        status="submitted",
        preferred_visit_date=date(2026, 11, 3),
        preferred_visit_time=time(9, 30),
    )
    db_session.add(invitation)
    await db_session.flush()
    for order in range(3):
        db_session.add(
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=order,
                approver_role_id=None,
                approver_user_id=approver.id,
                status="pending" if order >= pending_from else "approved",
            )
        )
    await db_session.commit()
    return invitation


_STATUS_TIMESTAMP_FIELDS = (
    "submitted_at",
    "approved_at",
    "checked_in_at",
    "checked_out_at",
    "denied_at",
    "archived_at",
    "approval_reverted_at",
    "rescheduled_at",
)


def _build_status_row(
    db_session: AsyncSession,
    branch_id: uuid.UUID,
    marker: str,
    status: str,
    **timestamps: datetime | None,
):
    """An invitation in `status` with every status timestamp pinned (None
    unless given) so the factory's random values can't affect the sort, and
    `marker` in the contact name so `search` isolates a test's own rows."""
    overrides: dict[str, Any] = dict.fromkeys(_STATUS_TIMESTAMP_FIELDS)
    overrides.update(timestamps)
    return _build_invitation(
        db_session,
        branch_id,
        status=status,
        primary_contact_full_name=f"{marker} {uuid.uuid4().hex[:6]}",
        **overrides,
    )


async def _list_rows(
    client: AsyncClient, token: str, marker: str, **params: Any
) -> list[dict[str, Any]]:
    response = await client.get(
        "/api/v1/invitations",
        params={"search": marker, "pageSize": 100, **params},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _invitation_with_host_step(
    db_session: AsyncSession, branch_id: uuid.UUID, host: User, **overrides
):
    """A `submitted` invitation whose `stepOrder` 0 step snapshots `host` as
    its approver — the shape specs/invitations/spec.md "Caller Lists
    Invitations Relevant to Themselves via relevantToMe" keys off.
    """
    invitation = _build_invitation(db_session, branch_id, host_id=host.id, **overrides)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=0,
            approver_role_id=None,
            approver_user_id=host.id,
        )
    )
    await db_session.commit()
    return invitation


async def _delegate_step(db_session: AsyncSession, invitation, delegate: User, delegated_by: User):
    """Directly assigns `delegate` to `invitation`'s `stepOrder` 1 step, for
    tests that only need a delegated step to already exist rather than
    exercising the delegate endpoint itself (that's `approvals/tests.py`'s
    job) — mirrors this module's other "unit-style" direct-repository setup
    (testing-standards.md §3).
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    step = InvitationApprovalStepFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation.id,
        step_order=1,
        approver_role_id=role.id,
    )
    db_session.add(step)
    await db_session.flush()
    updated = await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id, delegated_to_user_id=delegate.id, delegated_by_user_id=delegated_by.id
    )
    await db_session.commit()
    return updated


async def _invitation_with_role_step(
    db_session: AsyncSession, branch_id: uuid.UUID, role, **overrides
):
    """A `submitted` invitation whose `stepOrder` 1 step is role-identified
    for `role`, with no host step and no delegate — the shape spec.md "A
    role-holder sees an invitation whose current step needs their role"
    keys off.
    """
    overrides.setdefault("status", "submitted")
    overrides.setdefault("approved_at", None)
    invitation = _build_invitation(db_session, branch_id, **overrides)
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationApprovalStepFactory.build(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            step_order=1,
            approver_role_id=role.id,
            approver_user_id=None,
        )
    )
    await db_session.commit()
    return invitation


def _make_role_holder(db_session: AsyncSession, role, branch_id: uuid.UUID) -> User:
    """A user holding `role` via `UserBranchRole` at `branch_id` — no
    permissions attached, mirroring `relevantToMe`'s "no invitations:view
    required" contract.
    """
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"role-holder-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Role Holder",
        branch_roles=[branch_role],
    )
    db_session.add(test_user)
    return test_user


class _FakeInvitation:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str):
        # Falls back to `None` for any attribute a test didn't explicitly
        # set — every real `Invitation` column this module's email-template
        # rendering now reads (`host_id`, `purpose_of_visit`, etc.) is
        # nullable, so `None` is a safe default rather than requiring every
        # existing `_FakeInvitation(...)` call site in this file to list
        # every field it doesn't care about.
        return None


class _FakeScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def first(self):
        # `InvitationRepository.get_location`'s joined select reads a whole
        # (Branch, Department, Building) row.
        return self._value


class _FakeSession:
    def __init__(
        self, invitation, user=None, company=None, location=None, qr_code=None, tenant=None
    ) -> None:
        self._invitation = invitation
        self._user = user
        self._company = company
        self._location = location
        self._qr_code = qr_code
        self._tenant = tenant

    async def get(self, model, id_):
        return self._invitation

    async def execute(self, stmt):
        # Not a real `Select` evaluation — a canned result keyed off which
        # entity the statement targets, so each repository lookup a task
        # makes (`UserRepository.get_active`, `CompanyRepository.
        # get_singleton`, `InvitationRepository.get_location`/`get_qr_code`)
        # gets back the fake row the test actually configured.
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Company:
            return _FakeScalarResult(self._company)
        if entity is Branch:
            return _FakeScalarResult(self._location)
        if entity is InvitationQRCode:
            return _FakeScalarResult(self._qr_code)
        if entity is Tenant:
            return _FakeScalarResult(self._tenant)
        return _FakeScalarResult(self._user)


def _fake_tenant_session_scope(
    invitation, user=None, company=None, location=None, qr_code=None, tenant=None
):
    @asynccontextmanager
    async def _scope(schema_name: str):
        yield _FakeSession(
            invitation,
            user=user,
            company=company,
            location=location,
            qr_code=qr_code,
            tenant=tenant,
        )

    return _scope


_MAILPIT_BASE_URL = "http://localhost:8025/api/v1"


_MAILPIT_API_URL = f"{_MAILPIT_BASE_URL}/messages"


_MAILPIT_ASSET_BASE = "https://vmss-new-api.ddev.site:8443"


def _realistic_email_fakes() -> dict[str, Any]:
    """Org-chart and company rows shaped like real tenant data, so Mailpit
    sends look like production emails rather than bare test stubs
    (serve-email-images-by-url-and-complete-contact design.md Decision 5).
    """
    branch = SimpleNamespace(
        name="Technopark Campus",
        address="Phase 1",
        city="Trivandrum",
        contact_phone="+91 80000 22233",
        contact_email=None,
        contact_person_user_id=None,
    )
    return {
        "company": SimpleNamespace(
            legal_name="Acme Corp", logo_url=None, phone="+91 80 4000 1000", email=None
        ),
        "location": (branch, SimpleNamespace(name="Engineering"), SimpleNamespace(name="Tower A")),
    }


async def _persisted_approved_invitation(
    db_session: AsyncSession, branch: Branch, creator: User, *, qr_token_value: str
) -> Invitation:
    """A real invitation + QR row, so the signed QR URL in the delivered
    email resolves through the public route."""
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        branch_id=branch.id,
        created_by_user_id=creator.id,
        status="approved",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationQRCode(
            id=uuid.uuid4(),
            invitation_id=invitation.id,
            qr_token=qr_token_value,
            image_storage_key="k",
        )
    )
    await db_session.commit()
    return invitation


async def _find_mailpit_message(mailpit: AsyncClient, tracking_id: str, recipient: str) -> dict:
    list_response = await mailpit.get(_MAILPIT_API_URL, params={"limit": 50})
    assert list_response.status_code == 200
    matches = [
        m
        for m in list_response.json()["messages"]
        if tracking_id in m["Snippet"] and any(to["Address"] == recipient for to in m["To"])
    ]
    assert len(matches) == 1, (
        f"expected exactly one Mailpit message for {tracking_id}, found {len(matches)}"
    )
    detail_response = await mailpit.get(f"{_MAILPIT_BASE_URL}/message/{matches[0]['ID']}")
    assert detail_response.status_code == 200
    return detail_response.json()


def _image_srcs(html: str) -> list[str]:
    return [html_lib.unescape(src) for src in re.findall(r'<img src="([^"]+)"', html)]


async def _assert_url_images_and_fetch_qr(
    detail: dict, client: AsyncClient, expected_token: str
) -> None:
    # invitations spec "Delivered confirmation has no attachment strip and
    # a working QR URL": no attachments, no inline parts at all.
    assert detail["Attachments"] == []
    assert detail["Inline"] == []
    assert "cid:" not in detail["HTML"]
    srcs = _image_srcs(detail["HTML"])
    assert f"{_MAILPIT_ASSET_BASE}/api/v1/public/email-assets/guestify-logo.png" in srcs
    [qr_src] = [src for src in srcs if "/qr/" in src]
    assert qr_src.startswith(f"{_MAILPIT_ASSET_BASE}/api/v1/public/email-assets/")
    qr_response = await client.get(qr_src.removeprefix(_MAILPIT_ASSET_BASE))
    assert qr_response.status_code == 200
    assert qr_response.headers["content-type"] == "image/png"
    assert qr_response.content == await generate_qr_png(expected_token)


async def _branch_scoped_invitation_approver(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    """A caller whose only role grant is `invitations:approve` at
    `branch_id` — the approve-permission counterpart of
    `_branch_scoped_invitation_viewer` above.
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code="invitations:approve", description="invitations:approve"
    )
    role = RoleFactory.build(id=uuid.uuid4(), name="invitations-approver", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"approver-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Invitation Approver",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def _branch_scoped_user_with_permission(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID, *, permission_code: str
) -> User:
    """Generic counterpart of `_branch_scoped_invitation_viewer`/`_approver`
    above — a caller whose only role grant is `permission_code` at
    `branch_id`. One helper covers every new permission this capability
    adds instead of a hand-written near-duplicate per code.
    """
    label = permission_code.split(":")[-1]
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code=permission_code, description=permission_code
    )
    role = RoleFactory.build(id=uuid.uuid4(), name=f"invitations-{label}", permissions=[permission])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"{label}-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name=f"Invitation {label.title()}",
        branch_roles=[branch_role],
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


def _approved_invitation(db_session: AsyncSession, branch_id: uuid.UUID, **overrides):
    overrides.setdefault("status", "approved")
    overrides.setdefault("approved_at", datetime.now(UTC))
    overrides.setdefault("check_in_status", "unused")
    overrides.setdefault("expires_at", datetime.now(UTC) + timedelta(hours=1))
    # `InvitationFactory` (no default of its own for this nullable column)
    # generates a random `preferred_visit_date`, which could land in the
    # future and spuriously trip the new scheduled-date QR check-in gate
    # (qr-checkin-scheduling-photo-email) for every test in this module that
    # doesn't care about that dimension. Pinned to `None` here so those tests
    # keep exercising expiry-only gating; tests of the new behavior below
    # override it explicitly.
    overrides.setdefault("preferred_visit_date", None)
    return _build_invitation(db_session, branch_id, **overrides)


def _make_host(db_session: AsyncSession) -> User:
    return UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )


_EMAIL_TEMPLATE_NAMES = (
    "tracking_only",
    "visit_confirmation",
    "denial",
    "reschedule",
    "edit",
    "submission_role",
    "host_assigned",
    "poc_assigned",
)


async def _create_invitation_raw(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    payload: dict,
    include_primary_id_proof: bool = True,
    include_primary_photo: bool = True,
) -> Response:
    """Like `_create_invitation`, but lets a caller omit the primary
    contact's ID-proof/photo file parts entirely — needed to exercise a
    branch that has deactivated one of them.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    payload = await with_default_location(payload, branch.id)
    files = []
    if include_primary_id_proof:
        files.append(("primary_contact_id_proof_file", ("id.jpg", _jpeg_bytes(), "image/jpeg")))
    if include_primary_photo:
        files.append(("primary_contact_photo_file", ("selfie.jpg", _jpeg_bytes(), "image/jpeg")))
    return await client.post(
        "/api/v1/invitations",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=headers,
    )


async def _configure_and_publish_branch_field(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    field_key: str,
    changes: dict,
) -> None:
    """Admin-side setup shared by the tests below: fetches the branch's
    (form-builder-seeded) draft steps, finds `field_key` within `step_key`,
    PATCHes it with `changes`, then publishes the branch's scope so
    `create_invitation` actually reads the new configuration.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)
    field = next(f for f in step["fields"] if f["key"] == field_key)

    patch_response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}", json=changes, headers=headers
    )
    assert patch_response.status_code == 200, patch_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])


async def _create_and_publish_custom_field(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    key: str,
    field_type: str = "text",
    is_required: bool = False,
    options: list[str] | None = None,
    help_text: str | None = None,
    hide_label: bool = False,
) -> dict:
    """Admin-side setup: creates a new admin-authored field on `step_key`
    and publishes the branch's scope so `create_invitation` reads it.
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    steps_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert steps_response.status_code == 200, steps_response.text
    step = next(s for s in steps_response.json()["data"] if s["key"] == step_key)

    body: dict = {"key": key, "label": key.replace("_", " ").title(), "fieldType": field_type}
    if is_required:
        body["isRequired"] = True
    if options is not None:
        body["options"] = options
    if help_text is not None:
        body["helpText"] = help_text
    if hide_label:
        body["hideLabel"] = True
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=body, headers=headers
    )
    assert create_response.status_code == 201, create_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(steps_response.json()["data"])
    return create_response.json()["data"]


async def _update_and_publish_field_options(
    client: AsyncClient,
    token: str,
    branch: Branch,
    *,
    step_key: str,
    field_key: str,
    options: list[str],
    field_type: str | None = None,
) -> dict:
    """Admin-side setup: sets an existing (e.g. system-seeded) field's
    options (and, optionally, its `field_type`) and publishes the
    branch's scope so `create_invitation` reads it — used for
    `id_proof_type`/`vehicle_type` (make-id-proof-and-vehicle-type-
    configurable), whose options are editable even though the field
    itself was seeded, not admin-created; `field_type` additionally
    supports retyping a system field that isn't option-bearing by default
    (e.g. "Purpose of Visit") to `dropdown_select`/`checkbox_list`
    (make-system-field-types-editable).
    """
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    fields_response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert fields_response.status_code == 200, fields_response.text
    step = next(s for s in fields_response.json()["data"] if s["key"] == step_key)
    field = next(f for f in step["fields"] if f["key"] == field_key)

    body: dict[str, Any] = {"options": options}
    if field_type is not None:
        body["fieldType"] = field_type
    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}", json=body, headers=headers
    )
    assert update_response.status_code == 200, update_response.text

    publish_response = await client.post("/api/v1/form-builder/publish", headers=headers)
    assert publish_response.status_code == 200, publish_response.text
    _record_live_consent_field_ids(fields_response.json()["data"])
    return update_response.json()["data"]


async def _run_reschedule_task(monkeypatch, fake_invitation, *, qr_code=None) -> list[dict]:
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    monkeypatch.setattr(
        tasks, "tenant_session_scope", _fake_tenant_session_scope(fake_invitation, qr_code=qr_code)
    )
    result = await asyncio.to_thread(
        tasks.send_reschedule_notification.apply,
        kwargs={
            "request_id": "test",
            "tenant_schema": "tenant_acme_test",
            "invitation_id": str(uuid.uuid4()),
        },
    )
    result.get(propagate=True)
    return sent


def _reschedulable_invitation(status: str) -> _FakeInvitation:
    return _FakeInvitation(
        status=status,
        tracking_id="INV-RESCHED1",
        preferred_visit_date=date(2026, 12, 1),
        preferred_visit_time=time(15, 30),
        primary_contact_preferred_contact_method="email",
        primary_contact_email="visitor@example.com",
    )


class _UsersById:
    """Stands in for `UserRepository`: `get_active` by id, so each chain
    step can resolve a different person."""

    def __init__(self, people: dict[uuid.UUID, Any]) -> None:
        self._people = people

    def __call__(self, session):
        return self

    async def get_active(self, user_id: uuid.UUID):
        return self._people.get(user_id)


def _person(full_name: str, *, phone: str | None = None, email: str = "p@example.com"):
    return SimpleNamespace(full_name=full_name, phone_number=phone, email=email)


_HOST_ID, _BRANCH_CONTACT_ID = uuid.uuid4(), uuid.uuid4()


def _chain_branch(**overrides: Any) -> SimpleNamespace:
    return SimpleNamespace(
        **{"name": "Main Branch", "contact_person_user_id": _BRANCH_CONTACT_ID, **overrides}
    )


async def _contact_for(
    monkeypatch,
    *,
    poc_name: str | None = None,
    host_id: uuid.UUID | None = None,
    branch: SimpleNamespace | None,
    front_desk: str | None = "+91 80000 22233",
    people: dict[uuid.UUID, Any] | None = None,
) -> dict[str, str | None]:
    monkeypatch.setattr(tasks, "UserRepository", _UsersById(people or {}))
    invitation = _FakeInvitation(poc_name=poc_name, host_id=host_id)
    return await tasks._resolve_contact(
        None,  # type: ignore[arg-type]  # fakes stand in for the ORM objects
        invitation,  # type: ignore[arg-type]
        branch=branch,  # type: ignore[arg-type]
        front_desk_contact=front_desk,
    )


_PEOPLE = {
    _HOST_ID: _person("Rahul Verma", phone="+91 90000 33344"),
    _BRANCH_CONTACT_ID: _person("Anil Menon", phone="+91 90000 55566"),
}


async def _get_or_create_permission(db_session: AsyncSession, code: str) -> Permission:
    """Global `permissions.code` is unique, so reuse a row another fixture
    (e.g. `user`) may already have created instead of colliding with it.
    """
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    permission = PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
    db_session.add(permission)
    await db_session.flush()
    return permission


async def _host_role(db_session: AsyncSession):
    """The standard `host` role — delegation-only, holding `invitations:view`
    but not `invitations:view-all`, same as `auth/rbac_catalog.py` seeds it.
    """
    role = RoleFactory.build(
        id=uuid.uuid4(),
        name="host",
        permissions=[await _get_or_create_permission(db_session, "invitations:view")],
    )
    db_session.add(role)
    await db_session.flush()
    return role


async def _reception_to_host_invitation(
    db_session: AsyncSession,
    branch_id: uuid.UUID,
    host_role,
    *,
    step0_actor: User,
    resolved_host: User | None = None,
):
    """A `submitted` reception → host invitation whose `stepOrder` 0 step
    (default host role) is already approved by `step0_actor` and whose
    `stepOrder` 1 step (`host` role) is current and undelegated — the state
    the dev tenant's workflow sits in after Reception's own step is done.
    `resolved_host` models step 0 having been delegated to (and approved by)
    that host. Every step field the relevance rule reads is pinned, not left
    to the factory's RNG.
    """
    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    invitation = _build_invitation(
        db_session,
        branch_id,
        status="submitted",
        approved_at=None,
        host_id=resolved_host.id if resolved_host is not None else None,
    )
    db_session.add(invitation)
    await db_session.flush()
    step1 = InvitationApprovalStepFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation.id,
        step_order=1,
        approver_role_id=host_role.id,
        approver_user_id=None,
        status="pending",
        acted_by_user_id=None,
        acted_at=None,
        delegated_to_user_id=None,
        delegated_by_user_id=None,
        delegated_at=None,
    )
    db_session.add_all(
        [
            InvitationApprovalStepFactory.build(
                id=uuid.uuid4(),
                invitation_id=invitation.id,
                step_order=0,
                approver_role_id=reception.id,
                approver_user_id=None,
                status="approved",
                acted_by_user_id=step0_actor.id,
                acted_at=datetime.now(UTC),
                delegated_to_user_id=resolved_host.id if resolved_host is not None else None,
                delegated_by_user_id=None,
                delegated_at=None,
            ),
            step1,
        ]
    )
    await db_session.commit()
    return invitation, step1


async def _reception_holder(db_session: AsyncSession, branch_id: uuid.UUID) -> User:
    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    return _make_role_holder(db_session, reception, branch_id)


async def _relevant_tracking_ids(
    client: AsyncClient, issue_token: Callable[[User], str], caller: User
) -> set[str]:
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {issue_token(caller)}"},
    )
    assert response.status_code == 200, response.text
    return {row["trackingId"] for row in response.json()["data"]}


async def _get_detail(
    client: AsyncClient, issue_token: Callable[[User], str], caller: User, invitation_id
) -> Response:
    return await client.get(
        f"/api/v1/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {issue_token(caller)}"},
    )


class _FakeRedis:
    """In-memory stand-in for the two Redis calls `code_lockout` makes, so the
    lockout tests don't leak per-IP failure counters between runs."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None


def _sms_invitation(db_session: AsyncSession, branch_id: uuid.UUID, code: str, **overrides):
    overrides.setdefault("primary_contact_preferred_contact_method", "sms")
    overrides.setdefault("primary_contact_phone", "+919876543210")
    return _approved_invitation(db_session, branch_id, checkin_code=code, **overrides)


async def _code_device(db_session: AsyncSession, branch: Branch, **overrides):
    from factories import DeviceFactory

    device = DeviceFactory.build(id=uuid.uuid4(), branch_id=branch.id, **overrides)
    db_session.add(device)
    await db_session.commit()
    return device


_KOLKATA = "Asia/Kolkata"


def _checked_in_invitation(db_session: AsyncSession, branch_id: uuid.UUID):
    invitation = _build_invitation(
        db_session,
        branch_id,
        status="checked_in",
        check_in_status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    return invitation


async def _branch_scoped_user_with(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID, codes: tuple[str, ...]
) -> User:
    """A caller holding exactly `codes` at `branch_id`. Get-or-create on each
    `Permission` because `code` is unique across the global catalog and the
    `user` fixture (Admin) may already have inserted the same code in this
    test.
    """
    permissions = []
    for code in codes:
        existing = (
            await db_session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            existing = PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
            db_session.add(existing)
        permissions.append(existing)
    role = RoleFactory.build(
        id=uuid.uuid4(), name=f"revert-test-{uuid.uuid4().hex[:8]}", permissions=permissions
    )
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"revert-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Revert Caller",
        branch_roles=[branch_role],
    )
    db_session.add_all([role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


def _capture_revert_dispatch(monkeypatch) -> tuple[list[dict], list[dict]]:
    """Captures `(revert_email_calls, host_push_calls)`."""
    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_approval_revert_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    return email_calls, push_calls


async def _revert(
    client: AsyncClient, token: str, invitation_id: uuid.UUID, reason: Any
) -> Response:
    return await client.patch(
        f"/api/v1/invitations/{invitation_id}/revert-approval",
        json={"reason": reason},
        headers={"Authorization": f"Bearer {token}"},
    )


def _reverted_fake_invitation(**overrides) -> _FakeInvitation:
    fields = {
        "id": uuid.uuid4(),
        "status": "submitted",
        "approval_reverted_at": datetime.now(UTC),
        "tracking_id": "INV-REVERT01",
        "primary_contact_full_name": "Asha Rao",
        "primary_contact_preferred_contact_method": "email",
        "primary_contact_email": "asha@example.com",
        "primary_contact_phone": "+919876543210",
    }
    fields.update(overrides)
    return _FakeInvitation(**fields)


def _record_senders(monkeypatch) -> dict[str, list[dict]]:
    sent: dict[str, list[dict]] = {"email": [], "sms": [], "whatsapp": []}

    class _Recorder:
        def __init__(self, channel: str) -> None:
            self.channel = channel

        async def send(self, **kwargs):
            sent[self.channel].append(kwargs)

    for channel in sent:
        monkeypatch.setattr(notifications, f"{channel}_sender", _Recorder(channel))
    return sent


_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


_ALL_HEADERS = [column.header for column in invitation_export.COLUMNS]


def _names(**overrides: str | None) -> InvitationExportNames:
    fields: dict[str, str | None] = dict.fromkeys(InvitationExportNames._fields)
    fields.update(overrides)
    return InvitationExportNames(**fields)


def _base_header(header: str) -> str:
    """Strips a timestamp header's ` (<timezone>)` suffix."""
    return header.split(" (")[0]


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    """Rows keyed by header with the timezone suffix stripped, so callers
    needn't know which zone the tenant resolves to.
    """
    assert content.startswith(b"\xef\xbb\xbf")
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    return [{_base_header(key): value for key, value in row.items()} for row in reader]


def _csv_headers(content: bytes) -> list[str]:
    return next(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def _export_visitor(invitation_id: uuid.UUID, name: str) -> InvitationVisitor:
    return InvitationVisitorFactory.build(
        id=uuid.uuid4(),
        invitation_id=invitation_id,
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@visitor.example",
        phone="5550100",
        id_proof_type="passport",
        id_proof_storage_key=f"vmss:secret-id-proof-{name}",
        photo_storage_key=f"vmss:secret-photo-{name}",
    )


async def _service_export(db_session: AsyncSession, tenant: Any, **overrides: Any):
    kwargs: dict[str, Any] = {
        "branch_scope": "all",
        "relevant_to_user_id": None,
        "default_host_role_id": None,
        "status": None,
        "registration_type": None,
        "source": None,
        "search": None,
        "purpose_of_visit": None,
        "date_range": InvitationExportDateRange(),
        "export_format": ExportFormat.csv,
    }
    kwargs.update(overrides)
    return await invitations_service.export_invitations(db_session, tenant, **kwargs)


def _expired() -> datetime:
    return datetime.now(UTC) - timedelta(hours=1)


def _later() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


async def _sweep(session: AsyncSession) -> tuple[int, int]:
    return await tasks.sweep_visit_lifecycle(session, now=datetime.now(UTC))


async def _sweep_audits(db_session: AsyncSession, invitation_id: uuid.UUID) -> list[AuditLog]:
    stmt = select(AuditLog).where(
        AuditLog.entity_id == invitation_id,
        AuditLog.action.in_(("invitation_auto_checked_out", "invitation_archived")),
    )
    return list((await db_session.execute(stmt)).scalars().all())


def _archived_invitation(db_session: AsyncSession, branch_id: uuid.UUID, **overrides):
    overrides.setdefault("status", "archived")
    overrides.setdefault("archived_at", datetime.now(UTC))
    overrides.setdefault("expires_at", _expired())
    overrides.setdefault("preferred_visit_date", datetime.now(UTC).date() - timedelta(days=1))
    return _approved_invitation(db_session, branch_id, **overrides)


async def _noop_async(**kwargs: Any) -> None:
    return None


def _capture_reschedule_dispatch(monkeypatch) -> tuple[list[dict], list[dict]]:
    """Captures `(reschedule_email_calls, host_push_calls)`."""
    email_calls: list[dict] = []
    monkeypatch.setattr(
        tasks.send_reschedule_notification, "delay", lambda **kw: email_calls.append(kw)
    )
    push_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    return email_calls, push_calls


async def _reschedule(
    client: AsyncClient, token: str, invitation_id: uuid.UUID, visit_date: date
) -> Response:
    return await client.patch(
        f"/api/v1/invitations/{invitation_id}/reschedule",
        json={"preferredVisitDate": visit_date.isoformat(), "preferredVisitTime": "10:30:00"},
        headers={"Authorization": f"Bearer {token}"},
    )


async def _edit(
    client: AsyncClient, token: str, invitation_id: uuid.UUID, payload: dict
) -> Response:
    return await client.patch(
        f"/api/v1/invitations/{invitation_id}/edit",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def _capture_pushes(monkeypatch) -> tuple[list[dict], list[dict]]:
    """Captures `(user_push_calls, role_push_calls)`."""
    user_calls: list[dict] = []
    role_calls: list[dict] = []

    async def _fake_notify_user(**kwargs):
        user_calls.append(kwargs)

    async def _fake_notify_role_at_branch(tenant_db, **kwargs):
        role_calls.append(kwargs)

    monkeypatch.setattr(notifications_service, "notify_user", _fake_notify_user)
    monkeypatch.setattr(notifications_service, "notify_role_at_branch", _fake_notify_role_at_branch)
    return user_calls, role_calls


def _silence_visitor_dispatch(monkeypatch) -> None:
    for task in (
        tasks.send_denial_notification,
        tasks.send_approval_revert_notification,
        tasks.send_reschedule_notification,
    ):
        monkeypatch.setattr(task, "delay", lambda **kw: None)


async def _staff_pair(db_session: AsyncSession) -> tuple[User, User]:
    host = _make_host(db_session)
    poc = UserFactory.build(
        id=uuid.uuid4(), email=f"poc-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="POC"
    )
    db_session.add_all([host, poc])
    await db_session.flush()
    return host, poc


def _record_staff_emails(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    class _RecordingEmailSender:
        async def send(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(notifications, "email_sender", _RecordingEmailSender())
    return sent


def _pushed_user_ids(user_pushes: list[dict]) -> list[str]:
    return sorted(str(c["user_id"]) for c in user_pushes)


def _silence_edit_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(tasks.send_edit_notification, "delay", lambda **kw: None)
    monkeypatch.setattr(tasks.send_poc_creation_notification, "delay", lambda **kw: None)


async def _lookup_by_phone(client: AsyncClient, token: str, phone: str, **headers: str) -> Response:
    return await client.get(
        "/api/v1/invitations/lookup-by-phone",
        params={"phone": phone},
        headers={"Authorization": f"Bearer {token}", **headers},
    )
