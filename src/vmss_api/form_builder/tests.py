import uuid
from collections.abc import Callable

import pytest_asyncio
from httpx import AsyncClient

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """`GET /form-builder/effective` is public and resolves
    `settings.default_tenant_slug` when no token is presented — mirrors
    `visitors/tests.py`'s fixture of the same name.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _get_default_step(client: AsyncClient, token: str, key: str) -> dict:
    response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    assert response.status_code == 200
    steps = response.json()["data"]
    return next(s for s in steps if s["key"] == key)


# --- Steps: happy path, scope, permissions ----------------------------------


async def test_list_steps_seeds_and_returns_six_canonical_steps(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    assert response.status_code == 200
    steps = response.json()["data"]
    keys = [s["key"] for s in steps]
    assert keys == [
        "visitor_info",
        "visit_details",
        "carried_items",
        "vehicle_info",
        "consent_agreement",
        "review_confirm",
    ]
    visitor_info = next(s for s in steps if s["key"] == "visitor_info")
    assert visitor_info["isLocked"] is True
    full_name = next(f for f in visitor_info["fields"] if f["key"] == "full_name")
    assert full_name["isLocked"] is True
    assert full_name["isRequired"] is True


async def test_list_steps_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    assert response.status_code == 403


async def test_create_custom_step_success(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "nda_signing", "name": "NDA Signing"},
        headers=_auth(token),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["key"] == "nda_signing"
    assert body["isSystem"] is False
    assert body["isLocked"] is False


async def test_create_step_requires_manage_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "extra", "name": "Extra"},
        headers=_auth(token),
    )
    assert response.status_code == 403


async def test_locked_step_cannot_be_deactivated(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    visitor_info = await _get_default_step(client, token, "visitor_info")
    response = await client.patch(
        f"/api/v1/form-builder/steps/{visitor_info['id']}",
        json={"isActive": False},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_locked_step_cannot_be_deleted(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    visitor_info = await _get_default_step(client, token, "visitor_info")
    response = await client.delete(
        f"/api/v1/form-builder/steps/{visitor_info['id']}", headers=_auth(token)
    )
    assert response.status_code == 422


async def test_toggleable_step_can_be_deactivated(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    carried_items = await _get_default_step(client, token, "carried_items")
    response = await client.patch(
        f"/api/v1/form-builder/steps/{carried_items['id']}",
        json={"isActive": False},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["isActive"] is False


async def test_reorder_steps_persists(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    steps_response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    steps = steps_response.json()["data"]
    ids = [s["id"] for s in steps]
    reversed_ids = list(reversed(ids))
    response = await client.post(
        "/api/v1/form-builder/steps/reorder",
        json={"orderedIds": reversed_ids},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert [s["id"] for s in response.json()["data"]] == reversed_ids


# --- Branch scoping ----------------------------------------------------------


async def test_branch_scoped_step_is_independent_of_tenant_default(
    client: AsyncClient, user: User, branch: Branch, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    headers = {**_auth(token), "X-Branch-ID": str(branch.id)}

    create_response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "branch_only_step", "name": "Branch Only"},
        headers=headers,
    )
    assert create_response.status_code == 201

    branch_steps = (await client.get("/api/v1/form-builder/steps", headers=headers)).json()["data"]
    assert any(s["key"] == "branch_only_step" for s in branch_steps)
    assert all(
        s["branchId"] == str(branch.id) for s in branch_steps if s["key"] == "branch_only_step"
    )

    default_steps = (await client.get("/api/v1/form-builder/steps", headers=_auth(token))).json()[
        "data"
    ]
    assert not any(s["key"] == "branch_only_step" for s in default_steps)


async def test_branch_customization_clones_tenant_default_steps(
    client: AsyncClient, user: User, branch: Branch, issue_token: Callable[[User], str]
) -> None:
    """specs/form-builder/spec.md "Branch-specific configuration overrides
    the tenant default" / "starts from a copy ... rather than an empty
    form" — customizing a branch for the first time clones the six
    canonical steps rather than starting blank.
    """
    token = issue_token(user)
    headers = {**_auth(token), "X-Branch-ID": str(branch.id)}
    response = await client.get("/api/v1/form-builder/steps", headers=headers)
    assert response.status_code == 200
    keys = {s["key"] for s in response.json()["data"]}
    assert keys == {
        "visitor_info",
        "visit_details",
        "carried_items",
        "vehicle_info",
        "consent_agreement",
        "review_confirm",
    }


async def test_step_from_one_scope_not_visible_via_another_scope(
    client: AsyncClient, user: User, branch: Branch, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    default_step = await _get_default_step(client, token, "carried_items")

    headers = {**_auth(token), "X-Branch-ID": str(branch.id)}
    response = await client.get(
        f"/api/v1/form-builder/steps/{default_step['id']}/fields", headers=headers
    )
    assert response.status_code == 404


# --- Fields -------------------------------------------------------------------


async def test_create_field_option_required_type_without_options_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "badge_flag", "label": "Company Badge", "fieldType": "dropdown_select"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_create_field_success(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "company_badge",
            "label": "Company Badge",
            "fieldType": "checkbox_list",
            "options": ["yes"],
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    assert response.json()["data"]["key"] == "company_badge"


async def test_locked_field_cannot_have_required_or_active_toggled(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    full_name = next(f for f in step["fields"] if f["key"] == "full_name")
    response = await client.patch(
        f"/api/v1/form-builder/fields/{full_name['id']}",
        json={"isActive": False},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_toggleable_field_can_be_deactivated(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    additional_notes = next(f for f in step["fields"] if f["key"] == "additional_notes")
    response = await client.patch(
        f"/api/v1/form-builder/fields/{additional_notes['id']}",
        json={"isActive": False},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["isActive"] is False


async def test_conditional_visibility_dangling_reference_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "extra_consent",
            "label": "Extra Consent",
            "fieldType": "toggle_switch",
            "visibilityCondition": {
                "fieldKey": "does_not_exist",
                "operator": "equals",
                "value": "x",
            },
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_conditional_visibility_cycle_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")

    field_a = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={"key": "field_a", "label": "Field A", "fieldType": "toggle_switch"},
            headers=_auth(token),
        )
    ).json()["data"]
    field_b_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "field_b",
            "label": "Field B",
            "fieldType": "toggle_switch",
            "visibilityCondition": {"fieldKey": "field_a", "operator": "equals", "value": "true"},
        },
        headers=_auth(token),
    )
    assert field_b_response.status_code == 201

    cycle_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_a['id']}",
        json={
            "visibilityCondition": {"fieldKey": "field_b", "operator": "equals", "value": "true"}
        },
        headers=_auth(token),
    )
    assert cycle_response.status_code == 422


async def test_locked_field_cannot_be_deleted(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "vehicle_info")
    license_plate = next(f for f in step["fields"] if f["key"] == "license_plate")
    response = await client.delete(
        f"/api/v1/form-builder/fields/{license_plate['id']}", headers=_auth(token)
    )
    assert response.status_code == 422


async def test_reorder_fields_persists(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    ids = [f["id"] for f in step["fields"]]
    reversed_ids = list(reversed(ids))
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields/reorder",
        json={"orderedIds": reversed_ids},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert [f["id"] for f in response.json()["data"]] == reversed_ids


# --- Publish / effective form -------------------------------------------------


async def test_effective_form_falls_back_to_defaults_before_any_publish(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.get("/api/v1/form-builder/effective")
    assert response.status_code == 200
    steps = response.json()["data"]
    assert [s["key"] for s in steps] == [
        "visitor_info",
        "visit_details",
        "carried_items",
        "vehicle_info",
        "consent_agreement",
        "review_confirm",
    ]


async def test_publish_requires_manage_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert response.status_code == 403


async def test_publish_then_effective_form_reflects_deactivated_step(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    carried_items = await _get_default_step(client, token, "carried_items")
    await client.patch(
        f"/api/v1/form-builder/steps/{carried_items['id']}",
        json={"isActive": False},
        headers=_auth(token),
    )

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200
    assert publish_response.json()["data"]["version"] == 1

    effective_response = await client.get("/api/v1/form-builder/effective")
    assert effective_response.status_code == 200
    keys = [s["key"] for s in effective_response.json()["data"]]
    assert "carried_items" not in keys

    # Publishing again bumps the version and doesn't keep any history.
    second_publish = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert second_publish.json()["data"]["version"] == 2


async def test_publish_rejects_draft_with_dangling_visibility_reference(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """specs/form-builder/spec.md "Publishing Requires the Configuration To
    Be Internally Valid" — a field whose visibility target was since
    deleted must block publish, not just field-level create/update.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    target = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={"key": "target_field", "label": "Target", "fieldType": "toggle_switch"},
            headers=_auth(token),
        )
    ).json()["data"]
    dependent = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": "dependent_field",
                "label": "Dependent",
                "fieldType": "toggle_switch",
                "visibilityCondition": {
                    "fieldKey": "target_field",
                    "operator": "equals",
                    "value": "true",
                },
            },
            headers=_auth(token),
        )
    ).json()["data"]
    assert dependent["visibilityCondition"]["fieldKey"] == "target_field"

    await client.delete(f"/api/v1/form-builder/fields/{target['id']}", headers=_auth(token))

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 422


# --- Tenant isolation ----------------------------------------------------------


async def test_form_steps_tenant_schema_isolation(
    client: AsyncClient,
    user: User,
    issue_token: Callable[[User], str],
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2's mandatory tenant-isolation case: a custom
    step created in this tenant's schema must not be visible from a session
    bound to a different tenant's schema.
    """
    token = issue_token(user)
    create_response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "isolation_check", "name": "Isolation Check"},
        headers=_auth(token),
    )
    step_id = uuid.UUID(create_response.json()["data"]["id"])

    other_schema = "tenant_other_form_builder_test"
    await make_tenant_schema(other_schema)

    from vmss_api.form_builder.repository import FormStepRepository

    async with open_tenant_session(other_schema) as other_session:
        found = await FormStepRepository(other_session).get(step_id)
        assert found is None
