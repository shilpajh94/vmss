"""Loading and motion behaviour that keeps pages from jumping
(openspec change smooth-ui-motion-and-loading): a re-fetch keeps the loaded
content on screen, dialogs animate out before they leave the DOM, filter
panels collapse in place, and navigation starts the new page at the top.

The Branches register is the pilot page for every list page, so it carries
these checks. API responses are delayed through `page.route` so the
in-flight state is wide enough to assert on deterministically."""

import re

from playwright.sync_api import Page, Route, expect

from conftest import choose_option

BRANCH_LIST = re.compile(r"/api/v1/branches(\?.*)?$")


def hold_branch_list(page: Page) -> list[Route]:
    """Parks every branch-list GET until the test releases it with
    `release(held)`, so the in-flight state lasts exactly as long as the
    assertions need (sleeping inside a sync route handler would block the
    Playwright client too, making the window racy)."""
    held: list[Route] = []

    def handle(route: Route) -> None:
        if route.request.method == "GET":
            held.append(route)
        else:
            route.continue_()

    page.route(BRANCH_LIST, handle)
    return held


def release(page: Page, held: list[Route]) -> None:
    # Continue the parked requests before unrouting: unroute would otherwise
    # hand them on itself, and a second continue_() raises.
    while held:
        held.pop(0).continue_()
    page.unroute(BRANCH_LIST)


def open_branches(page: Page) -> None:
    page.goto("/admin/branches", wait_until="networkidle")
    expect(page.get_by_role("table")).to_be_visible()


def test_filter_change_keeps_rows_on_screen(as_role) -> None:
    admin = as_role("admin")
    open_branches(admin)
    first_row = admin.get_by_role("row").nth(1)
    expect(first_row).to_be_visible()

    admin.get_by_role("button", name="Filters").click()
    status = admin.get_by_label("Status")
    expect(status).to_be_visible()

    held = hold_branch_list(admin)
    choose_option(status, "Active")

    # While the filtered request is in flight: the old table is still
    # rendered (no spinner swap, no height collapse), marked busy.
    region = admin.locator("[aria-busy='true']")
    expect(region).to_be_visible()
    expect(admin.get_by_role("table")).to_be_visible()
    expect(admin.get_by_text("Loading branches…")).to_have_count(0)

    release(admin, held)
    expect(admin.locator("[aria-busy='true']")).to_have_count(0, timeout=10_000)
    expect(admin.get_by_role("table").or_(admin.get_by_text("No branches match these filters."))).to_be_visible()


def test_first_load_shows_a_table_skeleton(as_role) -> None:
    admin = as_role("admin")
    held = hold_branch_list(admin)
    admin.goto("/admin/branches")
    skeleton = admin.get_by_role("status", name="Loading branches…")
    expect(skeleton).to_be_visible()
    # The heading and actions are already in place above the skeleton.
    expect(admin.get_by_role("heading", name="Branches Register")).to_be_visible()
    expect(admin.get_by_role("button", name="Add Branch")).to_be_visible()
    release(admin, held)
    expect(admin.get_by_role("table")).to_be_visible(timeout=10_000)
    expect(skeleton).to_have_count(0)


def test_filter_panel_collapses_in_place(as_role) -> None:
    admin = as_role("admin")
    open_branches(admin)
    filters = admin.get_by_role("button", name="Filters")
    status = admin.get_by_label("Status")

    # Closed: present for the collapse animation, but not reachable.
    expect(status).not_to_be_visible()
    filters.click()
    expect(filters).to_have_attribute("aria-expanded", "true")
    expect(status).to_be_visible()
    filters.click()
    expect(filters).to_have_attribute("aria-expanded", "false")
    expect(status).not_to_be_visible()


def test_dialog_animates_out_before_unmounting(as_role) -> None:
    admin = as_role("admin")
    open_branches(admin)
    admin.get_by_role("button", name=re.compile(r"^Delete ")).first.click()
    dialog = admin.get_by_role("dialog", name="Delete Branch")
    expect(dialog).to_be_visible()
    message = dialog.get_by_text(re.compile(r'delete ".+"\?'))
    expect(message).to_be_visible()

    dialog.get_by_role("button", name="Cancel").click()
    # Mid-exit the dialog is still in the DOM, in its closing state, still
    # showing the branch name rather than "undefined".
    closing = admin.locator("[role='dialog'][data-state='closing']")
    expect(closing).to_have_count(1)
    expect(closing).not_to_contain_text("undefined")
    expect(admin.get_by_role("dialog")).to_have_count(0)


def test_escape_closes_dialog_and_returns_focus(as_role) -> None:
    admin = as_role("admin")
    open_branches(admin)
    trigger = admin.get_by_role("button", name=re.compile(r"^Delete ")).first
    trigger.click()
    expect(admin.get_by_role("dialog", name="Delete Branch")).to_be_visible()
    admin.keyboard.press("Escape")
    expect(admin.get_by_role("dialog")).to_have_count(0)
    expect(trigger).to_be_focused()


def test_navigation_resets_scroll_to_top(as_role) -> None:
    admin = as_role("admin")
    # Below `lg` the whole content region scrolls; the create form is long
    # enough to scroll at this height.
    admin.set_viewport_size({"width": 800, "height": 500})
    admin.goto("/admin/branches/new", wait_until="networkidle")
    main = admin.locator("main")
    main.evaluate("element => element.scrollTo({ top: element.scrollHeight })")
    assert main.evaluate("element => element.scrollTop") > 0

    # In-app navigation (not a reload, which would reset scroll anyway).
    admin.get_by_role("button", name="Back").click()
    expect(admin.get_by_role("heading", name="Branches Register")).to_be_visible()
    assert main.evaluate("element => element.scrollTop") == 0


def test_reduced_motion_dialog_still_works(as_role) -> None:
    admin = as_role("admin")
    admin.emulate_media(reduced_motion="reduce")
    open_branches(admin)
    admin.get_by_role("button", name=re.compile(r"^Delete ")).first.click()
    dialog = admin.get_by_role("dialog", name="Delete Branch")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Cancel").click()
    expect(admin.get_by_role("dialog")).to_have_count(0, timeout=1_000)
