"""Admin configuration journeys: a visitor category and its approval
workflow, the form builder's step editor, and the remaining admin
registries loading. Form-builder edits run only against the "QA Form
Builder Branch", never Main Branch's live registration form."""

import re

import pytest
from playwright.sync_api import expect

from conftest import Api, run_tag, select_matching


def test_admin_creates_category_and_workflow(as_role, api: Api) -> None:
    tag = run_tag()
    name, code = f"QA E2E Category {tag}", f"QA_E2E_{tag}"
    admin = as_role("admin")
    category_id = None
    try:
        admin.goto("/admin/visitor-categories/new", wait_until="networkidle")
        admin.get_by_label("Category Name").fill(name)
        admin.get_by_label("Category Code").fill(code)
        admin.get_by_label("Max Duration (minutes)").fill("90")
        admin.get_by_role("button", name="Save Category").click()
        expect(admin).not_to_have_url(re.compile(r"/new$"))
        category = next(
            c
            for c in api.call(
                "GET", "/api/v1/visitor-categories", None, params={"pageSize": 100, "search": name}
            )
            if c["code"] == code
        )
        category_id = category["id"]
        assert category["maxDurationMinutes"] == 90

        # Saving a category seeds its workflow with Reception as level 1.
        rules = api.call(
            "GET", "/api/v1/approval-workflow-rules", params={"visitorCategoryId": category_id}
        )
        assert [r["stepOrder"] for r in rules] == [1]

        admin.goto(f"/admin/workflows/{category_id}/edit", wait_until="networkidle")
        admin.get_by_role("button", name="Add Level").click()
        select_matching(admin.get_by_label("Level 2 approver"), "^host$")
        admin.get_by_role("button", name="Save Workflow").click()
        expect(admin).not_to_have_url(re.compile(r"/edit$"))
        rules = api.call(
            "GET", "/api/v1/approval-workflow-rules", params={"visitorCategoryId": category_id}
        )
        assert sorted(r["stepOrder"] for r in rules) == [1, 2]
    finally:
        if category_id:
            for rule in (
                api.call(
                    "GET",
                    "/api/v1/approval-workflow-rules",
                    params={"visitorCategoryId": category_id},
                )
                or []
            ):
                api.call("DELETE", f"/api/v1/approval-workflow-rules/{rule['id']}")
            api.call("DELETE", f"/api/v1/visitor-categories/{category_id}")


def test_admin_edits_a_form_builder_field(as_role, api: Api) -> None:
    tag = run_tag()
    step = api.call(
        "POST",
        "/api/v1/form-builder/steps",
        branch="QAFB",
        expect=201,
        json={"key": f"qa_e2e_{tag.lower()}", "name": f"QA E2E Step {tag}"},
    )
    field = api.call(
        "POST",
        f"/api/v1/form-builder/steps/{step['id']}/fields",
        branch="QAFB",
        expect=201,
        json={"key": f"qa_e2e_f_{tag.lower()}", "label": "QA E2E Field", "fieldType": "text"},
    )
    try:
        admin = as_role("admin")
        admin.goto("/admin/form-builder", wait_until="networkidle")
        select_matching(
            admin.get_by_role("main").locator("button[aria-haspopup=listbox]").first,
            "^QA Form Builder Branch$",
        )
        step_card = admin.get_by_text(f"QA E2E Step {tag}").locator(
            "xpath=ancestor::*[.//button[normalize-space()='Edit Fields']][1]"
        )
        step_card.get_by_role("button", name="Edit Fields").click()
        expect(admin.get_by_role("heading", level=1)).to_contain_text(f"QA E2E Step {tag}")

        admin.get_by_role("button", name="QA E2E Field Text Input").click()
        admin.get_by_label("Field Label").fill(f"QA E2E Field {tag} edited")
        # The styled track covers the switch input, so toggle via its label.
        admin.get_by_text("Required Field", exact=True).click()
        admin.get_by_role("button", name="Save Properties").click()
        expect(
            admin.get_by_role("button", name=re.compile(f"QA E2E Field {tag} edited"))
        ).to_be_visible()

        fields = api.call("GET", f"/api/v1/form-builder/steps/{step['id']}/fields", branch="QAFB")
        saved = next(f for f in fields if f["id"] == field["id"])
        assert saved["label"] == f"QA E2E Field {tag} edited"
        assert saved["isRequired"] is True

        admin.get_by_role("button", name="Publish Changes").click()
        confirm = admin.get_by_role("dialog")
        if confirm.count():
            confirm.get_by_role("button", name=re.compile("Publish")).last.click()
        expect(admin.get_by_text(re.compile("published", re.I)).first).to_be_visible()
    finally:
        api.call("DELETE", f"/api/v1/form-builder/steps/{step['id']}", branch="QAFB")
        api.call("POST", "/api/v1/form-builder/publish", branch="QAFB")


@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("/admin/roles", re.compile("Role")),
        ("/admin/kiosks", re.compile("Kiosk")),
        ("/admin/host-employees", re.compile("Employee")),
        ("/admin/invitations", re.compile("Invitation")),
        ("/admin/audit-trail", re.compile("Audit")),
        ("/admin/organisation-configs", re.compile("Organi[sz]ation")),
        ("/admin/reception-desks", re.compile("Desk")),
        ("/admin/security-gates", re.compile("Gate")),
    ],
)
def test_admin_registries_load(as_role, path: str, heading) -> None:
    page = as_role("admin")
    page.goto(path, wait_until="networkidle")
    expect(page.get_by_role("heading", level=1, name=heading)).to_be_visible()
    expect(page.get_by_text("Something went wrong")).to_have_count(0)
