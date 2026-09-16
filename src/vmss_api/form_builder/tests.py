import uuid
from collections.abc import Callable

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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


async def test_create_step_lands_before_review_confirm(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """A custom step must never land after the locked trailing run (Review
    & Confirm) — the pre-existing bug that made reordering (and the
    visitor-facing form) misbehave once two or more custom steps existed.
    """
    token = issue_token(user)

    first = (
        await client.post(
            "/api/v1/form-builder/steps",
            json={"key": "test_step_one", "name": "Test"},
            headers=_auth(token),
        )
    ).json()["data"]
    second = (
        await client.post(
            "/api/v1/form-builder/steps",
            json={"key": "test_step_two", "name": "Test 2"},
            headers=_auth(token),
        )
    ).json()["data"]

    steps_response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    keys = [s["key"] for s in steps_response.json()["data"]]
    assert keys == [
        "visitor_info",
        "visit_details",
        "carried_items",
        "vehicle_info",
        "consent_agreement",
        "test_step_one",
        "test_step_two",
        "review_confirm",
    ]
    # Creation-order relative to each other is preserved among the new steps.
    assert keys.index("test_step_one") < keys.index("test_step_two")
    assert first["id"] != second["id"]


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
    """Only the non-locked middle steps (Carried Items, Vehicle Info,
    Consent Agreement) are reordered here — Visitor Info, Visit Details, and
    Review & Confirm are locked and must stay in their first-two/last
    positions, per "Fields and Steps Are Explicitly Ordered".
    """
    token = issue_token(user)
    steps_response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    steps = steps_response.json()["data"]
    ids = [s["id"] for s in steps]
    locked_prefix, movable, locked_suffix = ids[:2], ids[2:5], ids[5:]
    reordered_ids = locked_prefix + list(reversed(movable)) + locked_suffix
    response = await client.post(
        "/api/v1/form-builder/steps/reorder",
        json={"orderedIds": reordered_ids},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert [s["id"] for s in response.json()["data"]] == reordered_ids


async def test_reorder_steps_rejects_locked_step_reposition(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    steps_response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    ids = [s["id"] for s in steps_response.json()["data"]]
    # Swap the two locked leading steps (Visitor Info, Visit Details) -
    # locked siblings must keep their relative position.
    swapped_ids = [ids[1], ids[0], *ids[2:]]
    response = await client.post(
        "/api/v1/form-builder/steps/reorder",
        json={"orderedIds": swapped_ids},
        headers=_auth(token),
    )
    assert response.status_code == 422

    unchanged_response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    assert [s["id"] for s in unchanged_response.json()["data"]] == ids


async def test_corrupted_step_order_is_repaired_on_next_access(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    issue_token: Callable[[User], str],
) -> None:
    """Simulates the outcome of the pre-existing bug (a custom step placed
    after Review & Confirm, as the old `create_step` would) directly at the
    DB layer, then asserts a subsequent read repairs the order without
    touching any step's or field's actual configuration.
    """
    from vmss_api.form_builder.repository import FormStepRepository

    token = issue_token(user)
    create_response = await client.post(
        "/api/v1/form-builder/steps",
        json={"key": "custom_step", "name": "Custom Step"},
        headers=_auth(token),
    )
    custom_step_id = uuid.UUID(create_response.json()["data"]["id"])

    repo = FormStepRepository(db_session)
    review_confirm = await repo.get_by_key(None, "review_confirm")
    custom_step = await repo.get(custom_step_id)
    assert review_confirm is not None
    assert custom_step is not None
    custom_step.order_index = review_confirm.order_index + 1
    await db_session.commit()

    response = await client.get("/api/v1/form-builder/steps", headers=_auth(token))
    steps = response.json()["data"]
    keys = [s["key"] for s in steps]
    assert keys == [
        "visitor_info",
        "visit_details",
        "carried_items",
        "vehicle_info",
        "consent_agreement",
        "custom_step",
        "review_confirm",
    ]
    # Nothing about the steps themselves changed - same ids, same names.
    custom_step_out = next(s for s in steps if s["key"] == "custom_step")
    assert custom_step_out["id"] == str(custom_step_id)
    assert custom_step_out["name"] == "Custom Step"


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


async def test_create_field_accepted_on_visitor_info(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """Every step accepts new admin-authored fields alongside its own
    seeded set, including Visitor Info - see `add-generic-custom-field-
    support/specs/form-builder/spec.md`'s "Fully Configurable Steps Accept
    Admin-Authored Fields".
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "test_field", "label": "Test field", "fieldType": "text"},
        headers=_auth(token),
    )
    assert response.status_code == 201
    assert response.json()["data"]["key"] == "test_field"

    fields_response = await client.get(
        f"/api/v1/form-builder/steps/{step['id']}/fields", headers=_auth(token)
    )
    assert any(f["key"] == "test_field" for f in fields_response.json()["data"])


async def test_create_field_accepted_on_visit_details(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "test_field", "label": "Test field", "fieldType": "text"},
        headers=_auth(token),
    )
    assert response.status_code == 201
    assert response.json()["data"]["key"] == "test_field"


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
    """Visit Details has 5 locked fields followed by 2 non-locked ones
    (`expected_duration`, `additional_notes`) - only the non-locked pair is
    reordered here; a locked field's position is covered separately by
    `test_reorder_fields_rejects_locked_field_reposition`.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    ids = [f["id"] for f in step["fields"]]
    locked_prefix, movable = ids[:5], ids[5:]
    reordered_ids = locked_prefix + list(reversed(movable))
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields/reorder",
        json={"orderedIds": reordered_ids},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert [f["id"] for f in response.json()["data"]] == reordered_ids


async def test_reorder_fields_rejects_locked_field_reposition(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    ids = [f["id"] for f in step["fields"]]
    # Swap the first two locked fields (registration_type, full_name) -
    # locked siblings must keep their relative position within the step.
    swapped_ids = [ids[1], ids[0], *ids[2:]]
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields/reorder",
        json={"orderedIds": swapped_ids},
        headers=_auth(token),
    )
    assert response.status_code == 422

    unchanged_response = await client.get(
        f"/api/v1/form-builder/steps/{step['id']}/fields", headers=_auth(token)
    )
    assert [f["id"] for f in unchanged_response.json()["data"]] == ids


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


async def test_publish_then_effective_form_reflects_deactivated_field(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """Field-level counterpart of
    `test_publish_then_effective_form_reflects_deactivated_step` -
    `publish()` filters on each field's `isActive` the same way it filters
    on `step.isActive`.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    additional_notes = next(f for f in step["fields"] if f["key"] == "additional_notes")
    deactivate_response = await client.patch(
        f"/api/v1/form-builder/fields/{additional_notes['id']}",
        json={"isActive": False},
        headers=_auth(token),
    )
    assert deactivate_response.status_code == 200

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    assert effective_response.status_code == 200
    effective_visit_details = next(
        s for s in effective_response.json()["data"] if s["key"] == "visit_details"
    )
    field_keys = [f["key"] for f in effective_visit_details["fields"]]
    assert "additional_notes" not in field_keys
    assert "expected_duration" in field_keys


async def test_publish_then_effective_form_includes_new_field(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "company_badge",
            "label": "Company Badge",
            "fieldType": "checkbox_list",
            "options": ["yes"],
        },
        headers=_auth(token),
    )
    assert create_response.status_code == 201

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_carried_items = next(
        s for s in effective_response.json()["data"] if s["key"] == "carried_items"
    )
    company_badge = next(
        (f for f in effective_carried_items["fields"] if f["key"] == "company_badge"), None
    )
    assert company_badge is not None
    assert company_badge["label"] == "Company Badge"
    assert company_badge["options"] == ["yes"]


async def test_publish_then_effective_form_reflects_edited_field(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    terms_field = next(f for f in step["fields"] if f["key"] == "terms_accepted")

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{terms_field['id']}",
        json={"label": "Updated Terms & Conditions"},
        headers=_auth(token),
    )
    assert update_response.status_code == 200

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_consent = next(
        s for s in effective_response.json()["data"] if s["key"] == "consent_agreement"
    )
    updated_field = next(f for f in effective_consent["fields"] if f["key"] == "terms_accepted")
    assert updated_field["label"] == "Updated Terms & Conditions"


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
