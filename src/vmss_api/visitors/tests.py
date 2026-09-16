import uuid
from collections.abc import Callable

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import ApprovalWorkflowRuleFactory, RoleFactory, VisitorCategoryFactory
from vmss_api.auth.models import Role, User
from vmss_api.core.config import settings
from vmss_api.core.schemas import SortOrder
from vmss_api.tenant.models import Tenant
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory
from vmss_api.visitors.repository import (
    ApprovalWorkflowRuleRepository,
    VisitorCategoryRepository,
)


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """`GET /visitor-categories` is public and resolves
    `settings.default_tenant_slug` (no JWT to read a tenant from) — mirrors
    `org_structure/tests.py`'s fixture of the same name.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


@pytest_asyncio.fixture
async def visitor_category(db_session: AsyncSession) -> VisitorCategory:
    category = VisitorCategoryFactory.build(id=uuid.uuid4(), name="Vendor", code="VENDOR")
    db_session.add(category)
    await db_session.commit()
    return category


@pytest_asyncio.fixture
async def approver_role(db_session: AsyncSession) -> Role:
    role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    db_session.add(role)
    await db_session.commit()
    return role


@pytest_asyncio.fixture
async def approval_workflow_rule(
    db_session: AsyncSession, visitor_category: VisitorCategory, approver_role: Role
) -> ApprovalWorkflowRule:
    rule = ApprovalWorkflowRuleFactory.build(
        id=uuid.uuid4(),
        visitor_category_id=visitor_category.id,
        approver_role_id=approver_role.id,
        step_order=1,
    )
    db_session.add(rule)
    await db_session.commit()
    return rule


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


# --- Visitor Category -----------------------------------------------------


async def test_create_visitor_category_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={
            "name": "Interview Candidate",
            "code": "INTERVIEW",
            "description": "Job applicants",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["code"] == "INTERVIEW"
    assert body["isActive"] is True


async def test_create_visitor_category_ignores_form_schema_field(
    client: AsyncClient, user: User
) -> None:
    """visitors delta spec "A category create/update request no longer
    accepts formSchema" — the field is silently ignored, not rejected,
    since category-specific fields are now authored in `form_builder`.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={
            "name": "Contractor",
            "code": "CONTRACTOR",
            "formSchema": [{"name": "company_name", "label": "Company", "fieldType": "text"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert "formSchema" not in response.json()["data"]


async def test_create_visitor_category_duplicate_code_conflict(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": "Another Vendor", "code": visitor_category.code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_create_visitor_category_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": "Vendor", "code": "VENDOR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_visitor_categories_no_auth_header_succeeds(
    client: AsyncClient, tenant: Tenant, visitor_category: VisitorCategory
) -> None:
    """Listing is public, same rationale as
    `org_structure/router.py::list_branches` — the pre-registration form
    needs a category picker before a visitor authenticates.
    """
    response = await client.get("/api/v1/visitor-categories")
    assert response.status_code == 200
    codes = {c["code"] for c in response.json()["data"]}
    assert visitor_category.code in codes


async def test_list_visitor_categories_no_permission_still_succeeds(
    client: AsyncClient,
    user_without_permissions: User,
    visitor_category: VisitorCategory,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/visitor-categories", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    codes = {c["code"] for c in response.json()["data"]}
    assert visitor_category.code in codes


async def test_get_visitor_category_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    visitor_category: VisitorCategory,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_visitor_categories_success(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/visitor-categories", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    codes = {c["code"] for c in response.json()["data"]}
    assert visitor_category.code in codes


async def test_list_visitor_categories_filtered_by_badge_color_nda_and_escort(
    client: AsyncClient, db_session: AsyncSession, user: User, visitor_category: VisitorCategory
) -> None:
    matching = VisitorCategoryFactory.build(
        id=uuid.uuid4(),
        name="Contractor",
        code="CONTRACTOR",
        badge_color="amber",
        nda_requirement="signed_pdf",
        escort_requirement="always_required",
    )
    db_session.add(matching)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    badge_response = await client.get(
        "/api/v1/visitor-categories?badgeColor=amber", headers=headers
    )
    assert badge_response.status_code == 200
    badge_codes = {c["code"] for c in badge_response.json()["data"]}
    assert matching.code in badge_codes
    assert visitor_category.code not in badge_codes

    nda_response = await client.get(
        "/api/v1/visitor-categories?ndaRequirement=signed_pdf", headers=headers
    )
    assert nda_response.status_code == 200
    nda_codes = {c["code"] for c in nda_response.json()["data"]}
    assert matching.code in nda_codes
    assert visitor_category.code not in nda_codes

    escort_response = await client.get(
        "/api/v1/visitor-categories?escortRequirement=always_required", headers=headers
    )
    assert escort_response.status_code == 200
    escort_codes = {c["code"] for c in escort_response.json()["data"]}
    assert matching.code in escort_codes
    assert visitor_category.code not in escort_codes


async def test_get_visitor_category_success(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(visitor_category.id)


async def test_get_visitor_category_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/visitor-categories/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_update_visitor_category_success(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        json={"description": "Updated description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["description"] == "Updated description"


async def test_update_visitor_category_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    visitor_category: VisitorCategory,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.put(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        json={"description": "Nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_delete_visitor_category_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    visitor_category: VisitorCategory,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.delete(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_delete_visitor_category_success(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404


async def test_create_visitor_category_after_soft_delete_reuses_code(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    """A soft-deleted category's `code` must not stay reserved forever —
    see openspec/changes/harden-visitor-types-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    delete_response = await client.delete(
        f"/api/v1/visitor-categories/{visitor_category.id}", headers=headers
    )
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": "New Vendor Name", "code": visitor_category.code},
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_create_visitor_category_after_soft_delete_reuses_name(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    """A soft-deleted category's `name` must not stay reserved forever —
    see openspec/changes/harden-visitor-types-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    delete_response = await client.delete(
        f"/api/v1/visitor-categories/{visitor_category.id}", headers=headers
    )
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": visitor_category.name, "code": "NEW-VENDOR-CODE"},
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_visitor_category_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, visitor_category: VisitorCategory
) -> None:
    other_schema = "tenant_other_test_visitor_category"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await VisitorCategoryRepository(other_session).get(visitor_category.id)
        assert found is None


async def test_visitor_category_list_page_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, visitor_category: VisitorCategory
) -> None:
    """Covers `GET /visitor-categories`'s `list_page` call —
    testing-standards.md §2, same shape as
    `test_visitor_category_repository_tenant_schema_isolation` above but for
    the paginated listing rather than the single-row `.get()`.
    """
    other_schema = "tenant_other_test_visitor_category_list"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await VisitorCategoryRepository(other_session).list_page(
            badge_color=None,
            nda_requirement=None,
            escort_requirement=None,
            page=1,
            page_size=20,
            sort_by="name",
            sort_order=SortOrder.asc,
        )
        assert rows == []
        assert total == 0


async def test_visitor_category_uniqueness_lookups_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, visitor_category: VisitorCategory
) -> None:
    """Covers `POST /visitor-categories`'s create-path uniqueness checks
    (`get_by_code`/`get_by_name`) — a code/name already used in a different
    tenant's schema must not collide here.
    """
    other_schema = "tenant_other_test_visitor_category_uniqueness"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        repo = VisitorCategoryRepository(other_session)
        assert await repo.get_by_code(visitor_category.code) is None
        assert await repo.get_by_name(visitor_category.name) is None


async def test_create_visitor_category_with_badge_and_policy_fields(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={
            "name": "Contractor",
            "code": "CONTRACTOR",
            "badgeColor": "#FF8800",
            "ndaRequirement": "signed_pdf",
            "escortRequirement": "always_required",
            "maxDurationMinutes": 480,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["badgeColor"] == "#FF8800"
    assert body["ndaRequirement"] == "signed_pdf"
    assert body["escortRequirement"] == "always_required"
    assert body["maxDurationMinutes"] == 480


async def test_update_visitor_category_policy_fields(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        json={"ndaRequirement": "optional", "escortRequirement": "gate_check_in_only"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["ndaRequirement"] == "optional"
    assert body["escortRequirement"] == "gate_check_in_only"


async def test_create_visitor_category_invalid_nda_requirement_rejected(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": "Bad Policy", "code": "BADPOLICY", "ndaRequirement": "not-a-real-option"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# --- Approval Workflow Rule -------------------------------------------------


async def test_create_approval_workflow_rule_success(
    client: AsyncClient, user: User, visitor_category: VisitorCategory, approver_role: Role
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": str(visitor_category.id),
            "stepOrder": 1,
            "approverRoleId": str(approver_role.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["visitorCategoryId"] == str(visitor_category.id)
    assert body["stepOrder"] == 1
    assert body["isMandatory"] is True


async def test_create_approval_workflow_rule_unknown_category_not_found(
    client: AsyncClient, user: User, approver_role: Role
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": str(uuid.uuid4()),
            "stepOrder": 1,
            "approverRoleId": str(approver_role.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_create_approval_workflow_rule_unknown_role_not_found(
    client: AsyncClient, user: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": str(visitor_category.id),
            "stepOrder": 1,
            "approverRoleId": str(uuid.uuid4()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_create_approval_workflow_rule_duplicate_step_conflict(
    client: AsyncClient,
    user: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    approver_role: Role,
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": str(approval_workflow_rule.visitor_category_id),
            "stepOrder": approval_workflow_rule.step_order,
            "approverRoleId": str(approver_role.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_create_approval_workflow_rule_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    visitor_category: VisitorCategory,
    approver_role: Role,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": str(visitor_category.id),
            "stepOrder": 1,
            "approverRoleId": str(approver_role.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_approval_workflow_rules_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/approval-workflow-rules",
        params={"visitorCategoryId": str(approval_workflow_rule.visitor_category_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_get_approval_workflow_rule_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_approval_workflow_rules_filtered_by_category(
    client: AsyncClient, user: User, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/approval-workflow-rules",
        params={"visitorCategoryId": str(approval_workflow_rule.visitor_category_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    assert str(approval_workflow_rule.id) in {r["id"] for r in body["data"]}


async def test_list_approval_workflow_rules_filtered_by_status(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    approver_role: Role,
) -> None:
    inactive_rule = ApprovalWorkflowRuleFactory.build(
        id=uuid.uuid4(),
        visitor_category_id=approval_workflow_rule.visitor_category_id,
        approver_role_id=approver_role.id,
        step_order=2,
        is_active=False,
    )
    db_session.add(inactive_rule)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/approval-workflow-rules",
        params={"status": "inactive"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["data"]}
    assert str(inactive_rule.id) in ids
    assert str(approval_workflow_rule.id) not in ids


async def test_get_approval_workflow_rule_success(
    client: AsyncClient, user: User, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(approval_workflow_rule.id)


async def test_update_approval_workflow_rule_success(
    client: AsyncClient, user: User, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        json={"isMandatory": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["isMandatory"] is False


async def test_update_approval_workflow_rule_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.put(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        json={"isMandatory": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_delete_approval_workflow_rule_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.delete(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_delete_approval_workflow_rule_success(
    client: AsyncClient, user: User, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404


async def test_create_approval_workflow_rule_after_soft_delete_reuses_step(
    client: AsyncClient,
    user: User,
    approval_workflow_rule: ApprovalWorkflowRule,
    approver_role: Role,
) -> None:
    """A soft-deleted rule's `(visitorCategoryId, stepOrder)` slot must not
    stay reserved forever — see
    openspec/changes/harden-visitor-types-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    delete_response = await client.delete(
        f"/api/v1/approval-workflow-rules/{approval_workflow_rule.id}", headers=headers
    )
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": str(approval_workflow_rule.visitor_category_id),
            "stepOrder": approval_workflow_rule.step_order,
            "approverRoleId": str(approver_role.id),
        },
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_approval_workflow_rule_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    other_schema = "tenant_other_test_workflow_rule"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await ApprovalWorkflowRuleRepository(other_session).get(approval_workflow_rule.id)
        assert found is None


async def test_approval_workflow_rule_list_page_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    """Covers `GET /approval-workflow-rules`'s `list_page` call —
    testing-standards.md §2, same shape as
    `test_approval_workflow_rule_repository_tenant_schema_isolation` above
    but for the paginated listing rather than the single-row `.get()`.
    """
    other_schema = "tenant_other_test_workflow_rule_list"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await ApprovalWorkflowRuleRepository(other_session).list_page(
            visitor_category_id=None,
            status=None,
            page=1,
            page_size=20,
            sort_by="step_order",
            sort_order=SortOrder.asc,
        )
        assert rows == []
        assert total == 0


async def test_approval_workflow_rule_uniqueness_lookup_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, approval_workflow_rule: ApprovalWorkflowRule
) -> None:
    """Covers `POST /approval-workflow-rules`'s create-path uniqueness check
    (`get_by_category_and_step`) — a `(visitorCategoryId, stepOrder)` pair
    already used in a different tenant's schema must not collide here.
    """
    other_schema = "tenant_other_test_workflow_rule_uniqueness"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await ApprovalWorkflowRuleRepository(other_session).get_by_category_and_step(
            approval_workflow_rule.visitor_category_id, approval_workflow_rule.step_order
        )
        assert found is None
