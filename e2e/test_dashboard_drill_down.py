"""Dashboard drill-down (openspec change fix-dashboard-count-accuracy):
every count a dashboard links from opens a board whose column totals add up
to that count (dashboard-insights "Every Dashboard Figure Matches the List
It Opens"), and the board keeps the drill-down as removable chips."""

import re
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, Response, expect

DASHBOARDS = [
    ("admin", "/admin/dashboard"),
    ("reception", "/reception/dashboard"),
    ("host", "/staff/dashboard"),
]
# "Expected Today: 4, 2 checked in so far. View these invitations" (tile) or
# "Denied: 3 visits. View these invitations" (status bar).
COUNT_LABEL = re.compile(r"^(?P<label>[^:]+): (?P<count>\d+)\b")


def _open_dashboard(as_role, role: str, path: str) -> Page:
    page = as_role(role)
    page.goto(path)
    expect(page.get_by_role("heading", level=1, name=re.compile(r"Good (Morning|Afternoon|Evening)"))).to_be_visible()
    page.wait_for_load_state("networkidle")
    return page


def _counted_links(page: Page) -> list[tuple[str, int, str]]:
    """(label, count, href) for every tile and status bar on the page."""
    links = page.locator("main a[href]").evaluate_all(
        "links => links.map(link => [link.getAttribute('aria-label') || '', link.getAttribute('href')])"
    )
    counted = []
    for aria_label, href in links:
        match = COUNT_LABEL.match(aria_label)
        if match and "invitationId" not in href:
            counted.append((match["label"], int(match["count"]), href))
    return counted


def _board_total(page: Page, open_board: Callable[[], None]) -> tuple[int, dict[str, int]]:
    """Sum of the first-page `total` of every column request the board makes
    — each column shows exactly that number in its header."""
    totals: dict[str, int] = {}

    def record(response: Response) -> None:
        url = urlparse(response.url)
        if not url.path.endswith("/api/v1/invitations") or response.request.method != "GET":
            return
        query = parse_qs(url.query)
        if query.get("page", ["1"])[0] == "1" and response.ok:
            totals[query.get("status", [""])[0]] = response.json()["pagination"]["total"]

    page.on("response", record)
    try:
        open_board()
        page.wait_for_load_state("networkidle")
    finally:
        page.remove_listener("response", record)
    assert totals, "the board made no list requests"
    return sum(totals.values()), totals


@pytest.mark.parametrize(("role", "path"), DASHBOARDS)
def test_every_dashboard_count_equals_the_board_it_opens(as_role, role: str, path: str) -> None:
    page = _open_dashboard(as_role, role, path)
    counted = _counted_links(page)
    assert len(counted) >= 4, counted  # at least the four tiles

    for label, count, href in counted:
        total, per_status = _board_total(page, lambda href=href: page.goto(href))
        assert total == count, f"{label}: dashboard {count}, board {total} {per_status} ({href})"
        page.go_back()
        page.wait_for_load_state("networkidle")


def test_selected_branch_carries_through_to_the_board(as_role, api) -> None:
    page = _open_dashboard(as_role, "admin", "/admin/dashboard")
    branch_select = page.locator("main").get_by_label("Branch", exact=True)
    if not branch_select.count():
        pytest.skip("the admin is authorized at a single branch only")
    branch_select.first.click()
    page.get_by_role("listbox", name="Branch").get_by_role("option").filter(has_not_text="All branches").first.click()
    page.wait_for_load_state("networkidle")

    for label, count, href in _counted_links(page):
        assert parse_qs(urlparse(href).query).get("branchId"), (label, href)
        total, per_status = _board_total(page, lambda href=href: page.goto(href))
        assert total == count, f"{label}: dashboard {count}, board {total} {per_status}"
        expect(page.get_by_role("group", name="From dashboard").get_by_text(re.compile(r"^Branch: "))).to_be_visible()
        page.go_back()
        page.wait_for_load_state("networkidle")


def test_removing_a_chip_widens_the_board(as_role) -> None:
    page = as_role("admin")
    narrow, _ = _board_total(page, lambda: page.goto("/admin/invitations?status=submitted&excludeExpired=true"))
    chips = page.get_by_role("group", name="From dashboard")
    expect(chips.get_by_text("Not expired", exact=True)).to_be_visible()

    wide, _ = _board_total(page, lambda: chips.get_by_role("button", name="Remove filter Not expired").click())
    expect(chips).to_have_count(0)
    assert wide >= narrow


def test_clear_filters_removes_the_dashboard_chips(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/invitations?upcoming=true&visitDateFrom=2026-10-20&visitDateTo=2026-10-26")
    chips = page.get_by_role("group", name="From dashboard")
    expect(chips.get_by_text("Upcoming only", exact=True)).to_be_visible()
    expect(chips.get_by_text(re.compile(r"^Visit date: "))).to_be_visible()
    page.get_by_role("button", name="Clear filters").click()
    expect(chips).to_have_count(0)


def test_malformed_drill_down_values_are_ignored(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/invitations?visitDateFrom=not-a-date&branchId=nope&upcoming=yes")
    expect(page.get_by_role("heading", level=1, name="Invitations")).to_be_visible()
    expect(page.get_by_role("group", name="From dashboard")).to_have_count(0)


def test_export_follows_the_drill_down(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/invitations?status=submitted&excludeExpired=true")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name=re.compile("^Export")).first.click()
    with page.expect_request(lambda request: "/api/v1/invitations/export" in request.url) as export_request:
        page.get_by_role("dialog").get_by_role("button", name=re.compile("^(Export|Download)")).click()
    query = parse_qs(urlparse(export_request.value.url).query)
    assert query.get("excludeExpired") == ["true"], query
