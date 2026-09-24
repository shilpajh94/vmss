import uuid
from collections.abc import Callable

import pytest
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


async def test_create_radio_button_field_without_options_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "shirt_size", "label": "Shirt Size", "fieldType": "radio_button"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_create_radio_button_field_with_options_succeeds(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "shirt_size",
            "label": "Shirt Size",
            "fieldType": "radio_button",
            "options": ["S", "M", "L"],
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["fieldType"] == "radio_button"
    assert data["options"] == ["S", "M", "L"]


async def test_create_checkbox_single_field_without_options_succeeds(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "terms_agreed",
            "label": "I agree to the terms",
            "fieldType": "checkbox_single",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["fieldType"] == "checkbox_single"
    assert data["options"] is None


@pytest.mark.parametrize("removed_type", ["dynamic_table", "rich_text_block", "signature_pad"])
async def test_create_field_with_removed_type_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], removed_type: str
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "legacy_field", "label": "Legacy Field", "fieldType": removed_type},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_list_fields_for_steps_groups_and_orders_fields_per_step(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    issue_token: Callable[[User], str],
) -> None:
    """Pins `service.list_fields_for_steps`'s per-step grouping/ordering
    behavior before its per-step-loop query is batched into one
    `WHERE step_id IN (...)` query (query-performance.md §2) — each step's
    fields must come back exactly as `FormFieldRepository.list_for_step`
    would return them individually: only that step's own fields, in
    `order_index` order, with no cross-step leakage.
    """
    from vmss_api.form_builder import service
    from vmss_api.form_builder.repository import FormStepRepository

    token = issue_token(user)
    carried_items = await _get_default_step(client, token, "carried_items")
    vehicle_info = await _get_default_step(client, token, "vehicle_info")

    async def _create_field(step_id: str, key: str) -> str:
        response = await client.post(
            f"/api/v1/form-builder/steps/{step_id}/fields",
            json={"key": key, "label": key, "fieldType": "checkbox_list", "options": ["yes"]},
            headers=_auth(token),
        )
        assert response.status_code == 201
        return response.json()["data"]["id"]

    ci_field_a = await _create_field(carried_items["id"], "ci_field_a")
    ci_field_b = await _create_field(carried_items["id"], "ci_field_b")
    vi_field_a = await _create_field(vehicle_info["id"], "vi_field_a")

    steps = await FormStepRepository(db_session).list_for_scope(None)
    fields_by_step = await service.list_fields_for_steps(db_session, steps)

    ci_step_id = uuid.UUID(carried_items["id"])
    vi_step_id = uuid.UUID(vehicle_info["id"])
    ci_new_field_ids = [
        str(f.id) for f in fields_by_step[ci_step_id] if f.key in {"ci_field_a", "ci_field_b"}
    ]
    assert ci_new_field_ids == [ci_field_a, ci_field_b]
    assert [str(f.id) for f in fields_by_step[vi_step_id] if f.key == "vi_field_a"] == [vi_field_a]
    # No cross-step leakage: vehicle_info's new field must not appear under carried_items.
    assert vi_field_a not in [str(f.id) for f in fields_by_step[ci_step_id]]


async def test_id_proof_type_options_cannot_be_emptied(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """make-id-proof-and-vehicle-type-configurable: `id_proof_type` is no
    longer exempt from the options-required rule — its options are now the
    real source of truth for what a submission may declare (unlike
    `visitor_category`, whose real options live in a separate catalog), so
    it needs the same non-empty-options guarantee any admin-authored
    dropdown has. Rejected at update time, before a publish could ever see
    an emptied state.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    id_proof_type = next(f for f in step["fields"] if f["key"] == "id_proof_type")
    response = await client.patch(
        f"/api/v1/form-builder/fields/{id_proof_type['id']}",
        json={"options": []},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_vehicle_type_options_cannot_be_emptied(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "vehicle_info")
    vehicle_type = next(f for f in step["fields"] if f["key"] == "vehicle_type")
    response = await client.patch(
        f"/api/v1/form-builder/fields/{vehicle_type['id']}",
        json={"options": []},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_visitor_category_remains_exempt_from_options_required(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """`visitor_category`'s real options come from the separate
    VisitorCategory catalog, not this row's own `options` — it stays
    exempt from the non-empty-options rule the narrowing in this change
    now applies to every other system dropdown field."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    visitor_category = next(f for f in step["fields"] if f["key"] == "visitor_category")
    assert visitor_category["options"] is None

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200, publish_response.text


async def test_create_static_text_field_success(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "terms_notice",
            "label": "Terms & Conditions",
            "fieldType": "static_text",
            "helpText": "By continuing you agree to our terms.",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["fieldType"] == "static_text"
    assert data["isRequired"] is False
    assert data["options"] is None
    assert data["helpText"] == "By continuing you agree to our terms."

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    published_step = next(
        s for s in effective_response.json()["data"] if s["key"] == "consent_agreement"
    )
    published_field = next(f for f in published_step["fields"] if f["key"] == "terms_notice")
    assert published_field["fieldType"] == "static_text"
    assert published_field["isRequired"] is False


async def test_create_static_text_field_as_required_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "terms_notice",
            "label": "Terms & Conditions",
            "fieldType": "static_text",
            "helpText": "By continuing you agree to our terms.",
            "isRequired": True,
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_create_static_text_field_without_help_text_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "terms_notice", "label": "Terms & Conditions", "fieldType": "static_text"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_update_static_text_field_as_required_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "consent_agreement")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "terms_notice",
            "label": "Terms & Conditions",
            "fieldType": "static_text",
            "helpText": "By continuing you agree to our terms.",
        },
        headers=_auth(token),
    )
    assert create_response.status_code == 201
    field_id = create_response.json()["data"]["id"]

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"isRequired": True},
        headers=_auth(token),
    )
    assert update_response.status_code == 422

    unchanged = await client.get(
        f"/api/v1/form-builder/steps/{step['id']}/fields", headers=_auth(token)
    )
    saved_field = next(f for f in unchanged.json()["data"] if f["id"] == field_id)
    assert saved_field["isRequired"] is False


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


async def test_locked_field_with_false_required_state_can_still_be_saved(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """Regression: the admin UI's save payload always resends every
    property it manages, including `isRequired`/`isActive` at their
    current (untouched) value — a locked field whose `isRequired` is
    already `false` (e.g. Email) must not be rejected just because that
    already-`false` value is present in the payload again. Only an actual
    attempted `true` → `false` transition is rejected."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    email = next(f for f in step["fields"] if f["key"] == "email")
    assert email["isLocked"] is True
    assert email["isRequired"] is False

    response = await client.patch(
        f"/api/v1/form-builder/fields/{email['id']}",
        json={"label": "Email Address", "isRequired": False, "isActive": True},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["label"] == "Email Address"


async def test_toggleable_system_field_can_be_saved_with_unchanged_field_type_resent(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """Regression: the admin UI's save payload always resends `fieldType`
    too — a system field's own (unchanged) type being present again must
    not be rejected as "changing" it."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    additional_notes = next(f for f in step["fields"] if f["key"] == "additional_notes")

    response = await client.patch(
        f"/api/v1/form-builder/fields/{additional_notes['id']}",
        json={"fieldType": additional_notes["fieldType"], "isActive": False},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["isActive"] is False


async def test_toggleable_retypeable_system_field_type_can_be_changed_directly(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """make-system-field-types-editable: a toggleable (unlocked) system
    field not in the type-locked exclusion set — Additional Notes is a
    plain `String` column with no cross-cutting backend consumer — is
    editable directly, no unlock step needed, the same as its other
    properties. Supersedes the old blanket "every isSystem field's type is
    fixed" rule (`fix-field-type-editing-and-lock-ux`)."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    additional_notes = next(f for f in step["fields"] if f["key"] == "additional_notes")
    assert additional_notes["isLocked"] is False
    assert additional_notes["isSystem"] is True

    response = await client.patch(
        f"/api/v1/form-builder/fields/{additional_notes['id']}",
        json={"fieldType": "text"},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["fieldType"] == "text"


async def test_locked_retypeable_system_field_type_can_be_changed(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """make-system-field-types-editable: a locked system field not in the
    type-locked exclusion set — Full Name is a plain `String(255)` column
    with no cross-cutting backend consumer — is retypeable. "Unlock to
    Edit" is a frontend-only UX guard (`add-static-text-field-and-unlock-
    toggle`'s design), not a backend permission boundary, so the API
    itself does not require any "unlocked" signal."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    full_name = next(f for f in step["fields"] if f["key"] == "full_name")
    assert full_name["isLocked"] is True
    assert full_name["isSystem"] is True

    response = await client.patch(
        f"/api/v1/form-builder/fields/{full_name['id']}",
        json={"fieldType": "textarea"},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["fieldType"] == "textarea"


@pytest.mark.parametrize(
    ("step_key", "field_key", "attempted_type"),
    [
        ("visitor_info", "registration_type", "text"),
        ("visitor_info", "email", "text"),
        ("visitor_info", "phone", "text"),
        ("visitor_info", "preferred_contact_method", "text"),
        ("visitor_info", "visitor_category", "text"),
        ("visitor_info", "id_proof_upload", "text"),
        ("visitor_info", "profile_photo", "text"),
        ("visit_details", "preferred_visit_date", "text"),
        ("visit_details", "preferred_visit_time", "text"),
    ],
)
async def test_excluded_system_field_type_cannot_be_changed(
    client: AsyncClient,
    user: User,
    issue_token: Callable[[User], str],
    step_key: str,
    field_key: str,
    attempted_type: str,
) -> None:
    """make-system-field-types-editable: fields whose value is consumed
    elsewhere as a specific structured type (notification dispatch,
    overstay detection, file storage, the Visitor Category catalog) stay
    permanently type-fixed, regardless of lock state."""
    token = issue_token(user)
    step = await _get_default_step(client, token, step_key)
    field = next(f for f in step["fields"] if f["key"] == field_key)
    original_type = field["fieldType"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field['id']}",
        json={"fieldType": attempted_type},
        headers=_auth(token),
    )
    assert response.status_code == 422

    unchanged = await _get_default_step(client, token, step_key)
    unchanged_field = next(f for f in unchanged["fields"] if f["key"] == field_key)
    assert unchanged_field["fieldType"] == original_type


async def test_retypeable_system_field_to_option_required_type_without_options_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    purpose_of_visit = next(f for f in step["fields"] if f["key"] == "purpose_of_visit")

    response = await client.patch(
        f"/api/v1/form-builder/fields/{purpose_of_visit['id']}",
        json={"fieldType": "dropdown_select"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_retypeable_system_field_to_option_required_type_with_options_succeeds(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    purpose_of_visit = next(f for f in step["fields"] if f["key"] == "purpose_of_visit")

    response = await client.patch(
        f"/api/v1/form-builder/fields/{purpose_of_visit['id']}",
        json={"fieldType": "dropdown_select", "options": ["Meeting", "Delivery", "Interview"]},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["fieldType"] == "dropdown_select"
    assert data["options"] == ["Meeting", "Delivery", "Interview"]


async def test_custom_field_type_can_be_changed(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text"},
        headers=_auth(token),
    )
    assert create_response.status_code == 201
    field_id = create_response.json()["data"]["id"]

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "textarea"},
        headers=_auth(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["fieldType"] == "textarea"

    fields_response = await client.get(
        f"/api/v1/form-builder/steps/{step['id']}/fields", headers=_auth(token)
    )
    saved = next(f for f in fields_response.json()["data"] if f["id"] == field_id)
    assert saved["fieldType"] == "textarea"


async def test_field_type_change_to_option_required_type_without_options_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text"},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "dropdown_select"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_field_type_change_to_option_required_type_with_options_succeeds(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text"},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "dropdown_select", "options": ["yes", "no"]},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["fieldType"] == "dropdown_select"
    assert data["options"] == ["yes", "no"]


async def test_field_type_change_to_radio_button_without_options_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text"},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "radio_button"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_field_type_change_away_from_option_bearing_type_clears_options(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "flavor",
            "label": "Flavor",
            "fieldType": "checkbox_list",
            "options": ["sweet", "savory"],
        },
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "text"},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["options"] is None


async def test_field_type_change_to_static_text_still_required_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text", "isRequired": True},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "static_text", "helpText": "Some content"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_field_type_change_to_static_text_without_help_text_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text"},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "static_text"},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_field_type_change_away_from_static_text_lifts_constraints(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "notice",
            "label": "Notice",
            "fieldType": "static_text",
            "helpText": "Some content",
        },
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    change_type_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "text"},
        headers=_auth(token),
    )
    assert change_type_response.status_code == 200

    require_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"isRequired": True},
        headers=_auth(token),
    )
    assert require_response.status_code == 200
    assert require_response.json()["data"]["isRequired"] is True


async def test_publish_then_effective_form_reflects_field_type_change(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "notes", "label": "Notes", "fieldType": "text"},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"fieldType": "textarea"},
        headers=_auth(token),
    )
    assert update_response.status_code == 200

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_step = next(
        s for s in effective_response.json()["data"] if s["key"] == "carried_items"
    )
    effective_field = next(f for f in effective_step["fields"] if f["key"] == "notes")
    assert effective_field["fieldType"] == "textarea"


async def test_publish_then_effective_form_reflects_retyped_system_field(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """make-system-field-types-editable: a retyped *system* field's new
    type publishes and resolves through `GET /form-builder/effective`
    exactly like a retyped admin-authored field's already does."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    additional_notes = next(f for f in step["fields"] if f["key"] == "additional_notes")

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{additional_notes['id']}",
        json={"fieldType": "text"},
        headers=_auth(token),
    )
    assert update_response.status_code == 200

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_step = next(
        s for s in effective_response.json()["data"] if s["key"] == "visit_details"
    )
    effective_field = next(f for f in effective_step["fields"] if f["key"] == "additional_notes")
    assert effective_field["fieldType"] == "text"


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


async def test_create_field_with_hide_label_true(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "company_badge",
            "label": "Company Badge",
            "fieldType": "text",
            "hideLabel": True,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["hideLabel"] is True


async def test_create_field_defaults_hide_label_false(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "company_badge", "label": "Company Badge", "fieldType": "text"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["hideLabel"] is False


async def test_update_field_toggles_hide_label(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "company_badge", "label": "Company Badge", "fieldType": "text"},
        headers=_auth(token),
    )
    field_id = create_response.json()["data"]["id"]

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"hideLabel": True},
        headers=_auth(token),
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["data"]["hideLabel"] is True

    fields_response = await client.get(
        f"/api/v1/form-builder/steps/{step['id']}/fields", headers=_auth(token)
    )
    saved = next(f for f in fields_response.json()["data"] if f["id"] == field_id)
    assert saved["hideLabel"] is True

    revert_response = await client.patch(
        f"/api/v1/form-builder/fields/{field_id}",
        json={"hideLabel": False},
        headers=_auth(token),
    )
    assert revert_response.status_code == 200, revert_response.text
    assert revert_response.json()["data"]["hideLabel"] is False


async def test_publish_then_effective_form_reflects_hide_label(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "company_badge",
            "label": "Company Badge",
            "fieldType": "text",
            "hideLabel": True,
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
        f for f in effective_carried_items["fields"] if f["key"] == "company_badge"
    )
    assert company_badge["hideLabel"] is True


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


async def test_publish_then_effective_form_reflects_edited_locked_field_label(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """add-static-text-field-and-unlock-toggle: the backend has never
    rejected a label change on a locked field (only `isActive`/
    `isRequired` -> `false` and delete/reorder are actually enforced) — the
    admin UI's new "Unlock to Edit" control lifts a frontend-only guard on
    top of this already-permissive contract (design.md Decision 6). This
    confirms an edit to a locked field's label persists and, once
    published, is what `GET /form-builder/effective` resolves — the exact
    same function both the staff and visitor registration flows read from
    (`invitations/service.py::create_invitation`,
    `registrations/service.py::create_walk_in_registration`), so a single
    check here covers both surfaces.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    full_name = next(f for f in step["fields"] if f["key"] == "full_name")
    assert full_name["isLocked"] is True

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{full_name['id']}",
        json={"label": "Visitor's Full Legal Name"},
        headers=_auth(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["label"] == "Visitor's Full Legal Name"

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_visitor_info = next(
        s for s in effective_response.json()["data"] if s["key"] == "visitor_info"
    )
    updated_field = next(f for f in effective_visitor_info["fields"] if f["key"] == "full_name")
    assert updated_field["label"] == "Visitor's Full Legal Name"


async def test_publish_default_scope_invalidates_branch_fallback_cache(
    client: AsyncClient, user: User, branch: Branch, issue_token: Callable[[User], str]
) -> None:
    """Regression test: a branch with no published config of its own reads
    the tenant-default snapshot (falls back), which used to get cached
    under the *branch's* cache key rather than the default's. Publishing
    the default scope only invalidated the default's own key, so a branch
    riding the fallback kept serving a stale snapshot until its 5-minute
    TTL expired on its own - the reported "toggling isRequired off doesn't
    take effect immediately" bug. Caching the fallback under the default's
    key means one publish invalidates it for every branch relying on it.
    """
    token = issue_token(user)
    branch_headers = {**_auth(token), "X-Branch-ID": str(branch.id)}

    # Warm the branch-scoped fallback cache before the branch has any
    # published config of its own.
    primed = await client.get("/api/v1/form-builder/effective", headers=branch_headers)
    assert primed.status_code == 200
    consent = next(s for s in primed.json()["data"] if s["key"] == "consent_agreement")
    terms_field = next(f for f in consent["fields"] if f["key"] == "terms_accepted")
    assert terms_field["isRequired"] is True

    # Edit and publish the tenant-default scope only - the branch never
    # publishes its own config.
    step = await _get_default_step(client, token, "consent_agreement")
    default_terms_field = next(f for f in step["fields"] if f["key"] == "terms_accepted")
    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{default_terms_field['id']}",
        json={"isRequired": False},
        headers=_auth(token),
    )
    assert update_response.status_code == 200

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    # The branch, still on the fallback path, must see the update
    # immediately rather than a stale cached copy.
    effective_response = await client.get("/api/v1/form-builder/effective", headers=branch_headers)
    assert effective_response.status_code == 200
    effective_consent = next(
        s for s in effective_response.json()["data"] if s["key"] == "consent_agreement"
    )
    effective_terms_field = next(
        f for f in effective_consent["fields"] if f["key"] == "terms_accepted"
    )
    assert effective_terms_field["isRequired"] is False


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


async def test_field_type_change_tenant_schema_isolation(
    client: AsyncClient,
    user: User,
    issue_token: Callable[[User], str],
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2 — make-system-field-types-editable: a
    system field's `field_type` change made under one tenant's schema
    must not be visible from a session bound to a different tenant's
    schema (each tenant has its own seeded copy of the same field key)."""
    token = issue_token(user)
    step = await _get_default_step(client, token, "visit_details")
    additional_notes = next(f for f in step["fields"] if f["key"] == "additional_notes")

    update_response = await client.patch(
        f"/api/v1/form-builder/fields/{additional_notes['id']}",
        json={"fieldType": "text"},
        headers=_auth(token),
    )
    assert update_response.status_code == 200

    other_schema = "tenant_other_field_type_isolation_test"
    await make_tenant_schema(other_schema)

    from sqlalchemy import select

    from vmss_api.form_builder.models import FormField

    async with open_tenant_session(other_schema) as other_session:
        # The other tenant's schema has no `form_fields` rows at all yet
        # (nothing seeds it until that tenant's own first `GET
        # /form-builder/steps` call) — so this tenant's field-type change
        # cannot possibly be visible there, by construction.
        result = await other_session.execute(
            select(FormField).where(FormField.key == "additional_notes")
        )
        assert result.scalar_one_or_none() is None


# --- fix-registration-host-role-crash: field-key uniqueness across a ------
# branch's entire active form (not only within one step) --------------------


async def test_create_field_key_collision_on_same_step_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """specs/form-builder/spec.md "Creating a Field With a Key Already Used
    on the Same Step Is Still Rejected" — today's existing per-step
    uniqueness check, unaffected by the new cross-step scope below.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    body = {"key": "duplicate_key", "label": "Duplicate", "fieldType": "text"}
    first = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=body, headers=_auth(token)
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields", json=body, headers=_auth(token)
    )
    assert second.status_code == 409


async def test_create_field_key_collision_on_different_active_step_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """specs/form-builder/spec.md "A Custom Field's Key Is Unique Across a
    Branch's Entire Active Form" — a key already used on one active step of
    the tenant-default form is rejected when creating a field with the same
    key on a *different* active step, since `custom_fields_for_invitation_scope`
    (`form_builder/validation.py`) merges every active step's fields into
    one flat by-key map at submission time.
    """
    token = issue_token(user)
    carried_items_step = await _get_default_step(client, token, "carried_items")
    first = await client.post(
        f"/api/v1/form-builder/steps/{carried_items_step['id']}/fields",
        json={"key": "shared_key", "label": "Shared Key", "fieldType": "text"},
        headers=_auth(token),
    )
    assert first.status_code == 201

    visit_details_step = await _get_default_step(client, token, "visit_details")
    second = await client.post(
        f"/api/v1/form-builder/steps/{visit_details_step['id']}/fields",
        json={"key": "shared_key", "label": "Shared Key", "fieldType": "text"},
        headers=_auth(token),
    )
    assert second.status_code == 409


async def test_create_field_distinct_keys_across_steps_succeed(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    carried_items_step = await _get_default_step(client, token, "carried_items")
    first = await client.post(
        f"/api/v1/form-builder/steps/{carried_items_step['id']}/fields",
        json={"key": "carried_items_only_key", "label": "First", "fieldType": "text"},
        headers=_auth(token),
    )
    assert first.status_code == 201

    visit_details_step = await _get_default_step(client, token, "visit_details")
    second = await client.post(
        f"/api/v1/form-builder/steps/{visit_details_step['id']}/fields",
        json={"key": "visit_details_only_key", "label": "Second", "fieldType": "text"},
        headers=_auth(token),
    )
    assert second.status_code == 201


# --- add-repeatable-field-groups: field groups -------------------------------


async def test_seeded_vehicle_info_group_is_locked_repeatable_and_owns_its_fields(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "vehicle_info")
    [group] = step["groups"]
    assert group["key"] == "vehicles"
    assert group["isSystem"] is True
    assert group["isLocked"] is True
    assert group["isRepeatable"] is True
    assert group["minInstances"] is None
    assert group["maxInstances"] is None
    grouped_field_keys = {f["key"] for f in step["fields"] if f["groupId"] == group["id"]}
    assert grouped_field_keys == {"vehicle_type", "license_plate", "make_model", "color"}


async def test_seeded_visitor_info_group_has_no_admin_editable_instance_range(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """add-repeatable-field-groups (revised): the group's `minInstances`/
    `maxInstances` aren't admin-editable — see
    `test_visitor_group_instance_range_cannot_be_set`. `isRepeatable` is now
    seeded `False` (a deliberate product decision to retire the
    group-visitor-count cap `maxInstances` used to enforce — see
    `invitations/tests.py::test_create_group_invitation_exceeding_former_max_visitors_accepted`),
    so `maxInstances` is seeded but no longer enforces anything.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    [group] = step["groups"]
    assert group["key"] == "visitors"
    assert group["isRepeatable"] is False
    assert group["minInstances"] is None
    assert group["maxInstances"] == settings.invitation_max_group_visitors


async def test_create_group_success(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "parcels", "name": "Parcels", "isRepeatable": True, "minInstances": 1},
        headers=_auth(token),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["key"] == "parcels"
    assert body["isSystem"] is False
    assert body["isLocked"] is False
    assert body["minInstances"] == 1
    assert body["maxInstances"] is None


async def test_create_group_requires_manage_permission(
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    other_token = issue_token(user_without_permissions)
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "parcels", "name": "Parcels"},
        headers=_auth(other_token),
    )
    assert response.status_code == 403


async def test_create_group_max_less_than_min_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={
            "key": "parcels",
            "name": "Parcels",
            "isRepeatable": True,
            "minInstances": 5,
            "maxInstances": 2,
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_group_key_collision_on_same_step_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    first = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "parcels", "name": "Parcels"},
        headers=_auth(token),
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "parcels", "name": "Parcels Again"},
        headers=_auth(token),
    )
    assert second.status_code == 409


async def test_group_key_collision_on_different_step_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    carried_items_step = await _get_default_step(client, token, "carried_items")
    first = await client.post(
        f"/api/v1/form-builder/steps/{carried_items_step['id']}/groups",
        json={"key": "shared_group_key", "name": "First"},
        headers=_auth(token),
    )
    assert first.status_code == 201

    visit_details_step = await _get_default_step(client, token, "visit_details")
    second = await client.post(
        f"/api/v1/form-builder/steps/{visit_details_step['id']}/groups",
        json={"key": "shared_group_key", "name": "Second"},
        headers=_auth(token),
    )
    assert second.status_code == 409


async def test_locked_vehicle_group_cannot_be_deleted(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "vehicle_info")
    [group] = step["groups"]
    response = await client.delete(
        f"/api/v1/form-builder/groups/{group['id']}", headers=_auth(token)
    )
    assert response.status_code == 422


async def test_locked_vehicle_group_cannot_be_made_non_repeatable(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "vehicle_info")
    [group] = step["groups"]
    response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}",
        json={"isRepeatable": False},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_locked_vehicle_group_instance_range_is_configurable(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "vehicle_info")
    [group] = step["groups"]
    response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}",
        json={"maxInstances": 5},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["maxInstances"] == 5


async def test_visitor_group_instance_range_cannot_be_set(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "visitor_info")
    [group] = step["groups"]
    response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}",
        json={"minInstances": 1},
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_delete_custom_group_ungroups_its_fields(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    group = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/groups",
            json={"key": "parcels", "name": "Parcels"},
            headers=_auth(token),
        )
    ).json()["data"]
    field_row = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": "parcel_weight",
                "label": "Parcel Weight",
                "fieldType": "text",
                "groupId": group["id"],
            },
            headers=_auth(token),
        )
    ).json()["data"]
    assert field_row["groupId"] == group["id"]

    delete_response = await client.delete(
        f"/api/v1/form-builder/groups/{group['id']}", headers=_auth(token)
    )
    assert delete_response.status_code == 204

    fields_response = await client.get(
        f"/api/v1/form-builder/steps/{step['id']}/fields", headers=_auth(token)
    )
    parcel_weight = next(f for f in fields_response.json()["data"] if f["key"] == "parcel_weight")
    assert parcel_weight["groupId"] is None


async def test_publish_then_effective_form_includes_group_definition(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    group = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/groups",
            json={"key": "parcels", "name": "Parcels", "isRepeatable": True, "minInstances": 1},
            headers=_auth(token),
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={
            "key": "parcel_weight",
            "label": "Parcel Weight",
            "fieldType": "text",
            "groupId": group["id"],
        },
        headers=_auth(token),
    )

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_carried_items = next(
        s for s in effective_response.json()["data"] if s["key"] == "carried_items"
    )
    published_group = next(g for g in effective_carried_items["groups"] if g["key"] == "parcels")
    assert published_group["isRepeatable"] is True
    assert published_group["minInstances"] == 1
    assert published_group["fieldKeys"] == ["parcel_weight"]


async def test_group_tenant_schema_isolation(
    client: AsyncClient,
    user: User,
    issue_token: Callable[[User], str],
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """testing-standards.md §2's mandatory tenant-isolation case: a custom
    field group created in this tenant's schema must not be visible from a
    session bound to a different tenant's schema.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    create_response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={"key": "isolation_group", "name": "Isolation Group"},
        headers=_auth(token),
    )
    group_id = uuid.UUID(create_response.json()["data"]["id"])

    other_schema = "tenant_other_field_group_test"
    await make_tenant_schema(other_schema)

    from vmss_api.form_builder.repository import FormFieldGroupRepository

    async with open_tenant_session(other_schema) as other_session:
        found = await FormFieldGroupRepository(other_session).get(group_id)
        assert found is None


# --- add-repeatable-field-groups (revised): group conditional visibility ----


async def test_create_group_with_valid_visibility_condition_succeeds(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    watched_field = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        json={"key": "requires_extra_gear", "label": "Extra Gear?", "fieldType": "text"},
        headers=_auth(token),
    )
    watched_field_key = watched_field.json()["data"]["key"]

    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={
            "key": "extra_gear_details",
            "name": "Extra Gear Details",
            "visibilityCondition": {
                "fieldKey": watched_field_key,
                "operator": "equals",
                "value": "yes",
            },
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["visibilityCondition"] == {
        "fieldKey": watched_field_key,
        "operator": "equals",
        "value": "yes",
    }


async def test_create_group_with_dangling_visibility_condition_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    response = await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={
            "key": "conditional_group",
            "name": "Conditional Group",
            "visibilityCondition": {
                "fieldKey": "does_not_exist",
                "operator": "equals",
                "value": "yes",
            },
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_update_group_visibility_condition_self_reference_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    """specs/form-builder/spec.md "A Field Group May Declare Conditional
    Visibility" — a group's condition cannot watch one of its own member
    fields.
    """
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    group = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/groups",
            json={"key": "self_ref_group", "name": "Self Ref Group"},
            headers=_auth(token),
        )
    ).json()["data"]
    member_field = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={
                "key": "member_field",
                "label": "Member Field",
                "fieldType": "text",
                "groupId": group["id"],
            },
            headers=_auth(token),
        )
    ).json()["data"]

    response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}",
        json={
            "visibilityCondition": {
                "fieldKey": member_field["key"],
                "operator": "equals",
                "value": "x",
            }
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_update_group_visibility_condition_referencing_other_step_rejected(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    carried_items_step = await _get_default_step(client, token, "carried_items")
    group = (
        await client.post(
            f"/api/v1/form-builder/steps/{carried_items_step['id']}/groups",
            json={"key": "cross_step_group", "name": "Cross Step Group"},
            headers=_auth(token),
        )
    ).json()["data"]

    response = await client.patch(
        f"/api/v1/form-builder/groups/{group['id']}",
        json={
            "visibilityCondition": {
                "fieldKey": "registration_type",  # lives on visitor_info, not carried_items
                "operator": "equals",
                "value": "group",
            }
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


async def test_publish_then_effective_form_includes_group_visibility_condition(
    client: AsyncClient, user: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user)
    step = await _get_default_step(client, token, "carried_items")
    watched_field = (
        await client.post(
            f"/api/v1/form-builder/steps/{step['id']}/fields",
            json={"key": "trigger_field", "label": "Trigger Field", "fieldType": "text"},
            headers=_auth(token),
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/form-builder/steps/{step['id']}/groups",
        json={
            "key": "conditional_parcels",
            "name": "Conditional Parcels",
            "visibilityCondition": {
                "fieldKey": watched_field["key"],
                "operator": "equals",
                "value": "yes",
            },
        },
        headers=_auth(token),
    )

    publish_response = await client.post("/api/v1/form-builder/publish", headers=_auth(token))
    assert publish_response.status_code == 200

    effective_response = await client.get("/api/v1/form-builder/effective")
    effective_carried_items = next(
        s for s in effective_response.json()["data"] if s["key"] == "carried_items"
    )
    published_group = next(
        g for g in effective_carried_items["groups"] if g["key"] == "conditional_parcels"
    )
    assert published_group["visibilityCondition"] == {
        "fieldKey": watched_field["key"],
        "operator": "equals",
        "value": "yes",
    }
