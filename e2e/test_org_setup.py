"""Org structure set-up through the admin portal: a branch, a building in
it, a floor and a department, each created through its form and edited
where the portal offers it. Everything created is removed again through the
API afterwards, children first (a branch with active children can't be
deleted).

Forms are filled only once their page has settled: input typed while a
form's reference data is still loading is discarded (QA report F13)."""

import re

from playwright.sync_api import Page, expect

from conftest import Api, choose_option, run_tag


def row(page: Page, text: str):
    return page.get_by_role("row").filter(has_text=text)


def test_admin_creates_and_edits_org_structure(as_role, api: Api) -> None:
    tag = run_tag()
    branch_name, branch_code = f"QA E2E Branch {tag}", f"E2E{tag}"
    building_name = f"QA E2E Tower {tag}"
    created: list[tuple[str, str]] = []
    admin = as_role("admin")
    try:
        admin.goto("/admin/branches/new", wait_until="networkidle")
        admin.get_by_label("Branch Name").fill(branch_name)
        admin.get_by_label("Branch Code").fill(branch_code)
        admin.get_by_label("Location / City").fill("QA City")
        choose_option(admin.get_by_label("Country"), index=0)
        # Validated as required although the label carries no "*" (QA report F12).
        admin.get_by_label("Physical Address").fill("1 QA Street")
        choose_option(admin.get_by_label("Contact Person (Regional Admin)"), index=0)
        admin.get_by_label("Contact Email Address").fill(f"qa.e2e.{tag.lower()}@example.com")
        admin.get_by_label("Contact Phone").fill("+919876543210")
        admin.get_by_role("button", name="Create Branch").click()
        expect(admin).not_to_have_url(re.compile(r"/admin/branches/new$"))
        admin.goto("/admin/branches")
        expect(row(admin, branch_code)).to_be_visible()
        branch_id = next(
            b["id"]
            for b in api.call(
                "GET", "/api/v1/branches", None, branch=None, params={"pageSize": 100}
            )
            if b["code"] == branch_code
        )
        created.append(("branches", branch_id))

        row(admin, branch_code).get_by_role("button", name=f"Edit {branch_name}").click()
        admin.get_by_label("Location / City").fill("QA City Edited")
        admin.get_by_role("button", name=re.compile("Save|Update")).last.click()
        # The modal closes once the PUT has succeeded; navigating before then
        # cancels the request.
        expect(admin.get_by_role("dialog", name="Edit Branch")).to_be_hidden()
        admin.goto("/admin/branches")
        expect(row(admin, branch_code)).to_contain_text("QA City Edited")

        admin.goto("/admin/buildings/new", wait_until="networkidle")
        admin.get_by_label("Building Name").fill(building_name)
        choose_option(admin.get_by_label("Branch"), branch_name)
        admin.get_by_label("Building Code").fill(f"B{branch_code}")
        admin.get_by_role("button", name="Save Building").click()
        expect(admin).not_to_have_url(re.compile(r"/admin/buildings/new$"))
        building = next(
            b
            for b in api.call("GET", "/api/v1/buildings", branch=None)
            if b["name"] == building_name
        )
        created.append(("buildings", building["id"]))

        admin.goto("/admin/floors/new", wait_until="networkidle")
        admin.get_by_label("Floor Name").fill(f"QA E2E Floor {tag}")
        choose_option(admin.get_by_label("Building"), building_name)
        admin.get_by_role("button", name="Save Floor").click()
        expect(admin).not_to_have_url(re.compile(r"/admin/floors/new$"))
        floor = next(
            f
            for f in api.call("GET", "/api/v1/floors", branch=None, params={"pageSize": 100})
            if f["name"] == f"QA E2E Floor {tag}"
        )
        created.append(("floors", floor["id"]))

        admin.goto("/admin/departments/new", wait_until="networkidle")
        admin.get_by_label("Department Name").fill(f"QA E2E Dept {tag}")
        choose_option(admin.get_by_label("Branch"), branch_name)
        admin.get_by_label("Department Code").fill(f"D{branch_code}")
        admin.get_by_role("button", name="Save Department").click()
        expect(admin).not_to_have_url(re.compile(r"/admin/departments/new$"))
        department = next(
            d
            for d in api.call("GET", "/api/v1/departments", branch=None, params={"pageSize": 100})
            if d["name"] == f"QA E2E Dept {tag}"
        )
        created.append(("departments", department["id"]))
    finally:
        for resource, entity_id in reversed(created):
            api.call("DELETE", f"/api/v1/{resource}/{entity_id}", branch=None)
