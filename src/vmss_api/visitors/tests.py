import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import ApprovalWorkflowRuleFactory, RoleFactory, VisitorCategoryFactory
from vmss_api.auth.models import Role, User
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory
from vmss_api.visitors.repository import (
    ApprovalWorkflowRuleRepository,
    VisitorCategoryRepository,
)


@pytest_asyncio.fixture
async def visitor_category(db_session: AsyncSession) -> VisitorCategory:
    category = VisitorCategoryFactory.build(
        id=uuid.uuid4(),
        name="Vendor",
        code="VENDOR",
        form_schema=[
            {
                "name": "company_name",
                "label": "Company Name",
                "fieldType": "text",
                "required": True,
                "options": None,
                "helpText": None,
            }
        ],
    )
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
            "formSchema": [
                {
                    "name": "position_applied",
                    "label": "Position Applied For",
                    "fieldType": "text",
                    "required": True,
                }
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["code"] == "INTERVIEW"
    assert body["formSchema"][0]["name"] == "position_applied"
    assert body["isActive"] is True


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


async def test_create_visitor_category_duplicate_form_field_names_rejected(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={
            "name": "Contractor",
            "code": "CONTRACTOR",
            "formSchema": [
                {"name": "company_name", "label": "Company", "fieldType": "text"},
                {"name": "company_name", "label": "Company Again", "fieldType": "text"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_create_visitor_category_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": "Vendor", "code": "VENDOR"},
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
    client: AsyncClient, user_without_permissions: User, visitor_category: VisitorCategory
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.put(
        f"/api/v1/visitor-categories/{visitor_category.id}",
        json={"description": "Nope"},
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


async def test_create_visitor_category_select_field_without_options_rejected(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/visitor-categories",
        json={
            "name": "Delivery Person",
            "code": "DELIVERY",
            "formSchema": [
                {"name": "carrier", "label": "Carrier", "fieldType": "select", "options": []}
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_visitor_category_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, visitor_category: VisitorCategory
) -> None:
    other_schema = "tenant_other_test_visitor_category"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await VisitorCategoryRepository(other_session).get(visitor_category.id)
        assert found is None


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
) -> None:
    token = await _login(client, user_without_permissions.email)
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
