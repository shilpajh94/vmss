"""Live dashboards (openspec change live-dashboards-and-analytics):
every control works, deep links land on a filtered board, charts follow
the range toggle, a host sees only their own figures, and no dashboard
scrolls sideways from phone to desktop."""

import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

DASHBOARDS = [
    ("admin", "/admin/dashboard", "/admin/invitations"),
    ("reception", "/reception/dashboard", "/staff/invitations"),
    ("host", "/staff/dashboard", "/staff/invitations"),
]
KNOWN_STATUSES = {"submitted", "approved", "checked_in", "checked_out", "denied", "archived"}
DRILL_DOWN_PARAMS = {"status", "visitDateFrom", "visitDateTo", "upcoming", "excludeExpired", "branchId"}


def _open_dashboard(as_role, role: str, path: str) -> Page:
    page = as_role(role)
    page.goto(path)
    expect(page.get_by_role("heading", level=1, name=re.compile(r"Good (Morning|Afternoon|Evening)"))).to_be_visible()
    return page


@pytest.mark.parametrize(("role", "path", "board"), DASHBOARDS)
def test_every_dashboard_control_has_a_destination(as_role, role: str, path: str, board: str) -> None:
    """dashboard-insights "Every Dashboard Control Is Functional": each link
    targets the role's board with an invitation id or a drill-down of known
    statuses and filters, and each button visibly changes state when pressed."""
    page = _open_dashboard(as_role, role, path)
    main = page.locator("main")

    hrefs = main.locator("a[href]").evaluate_all("links => links.map(link => link.getAttribute('href'))")
    assert hrefs, "the dashboard rendered no links"
    for href in hrefs:
        parsed = urlparse(href)
        assert parsed.path == board, href
        query = parse_qs(parsed.query)
        if query.get("invitationId"):
            continue
        assert query and set(query) <= DRILL_DOWN_PARAMS, href
        assert set(query.get("status", [])) <= KNOWN_STATUSES, href

    toggles = main.locator("button[aria-pressed]")
    assert toggles.count() >= 2
    for index in range(toggles.count()):
        toggle = toggles.nth(index)
        if toggle.get_attribute("aria-pressed") == "false":
            toggle.click()
            expect(toggle).to_have_attribute("aria-pressed", "true")

    # Every other button on the page, besides dropdown triggers like the
    # branch selector, is the error state's "Try again", which only exists
    # when loading failed.
    plain_buttons = main.locator("button:not([aria-pressed]):not([aria-haspopup])")
    expect(plain_buttons).to_have_count(0)


@pytest.mark.parametrize(
    ("role", "path", "tile", "board", "query", "label", "chip"),
    [
        ("admin", "/admin/dashboard", "Pending Approval", "/admin/invitations", "status=submitted&excludeExpired=true", "Requested", "Not expired"),
        ("admin", "/admin/dashboard", "On-Site Now", "/admin/invitations", "status=checked_in", "Checked-in", None),
        ("reception", "/reception/dashboard", "Upcoming Visitors", "/staff/invitations", "upcoming=true", None, "Upcoming only"),
        ("host", "/staff/dashboard", "Inside Now", "/staff/invitations", "status=checked_in", "Checked-in", None),
    ],
)
def test_kpi_tile_opens_the_filtered_board(
    as_role, role: str, path: str, tile: str, board: str, query: str, label: str | None, chip: str | None
) -> None:
    """dashboard-insights "KPI Tiles Link to the Matching Invitations"."""
    page = _open_dashboard(as_role, role, path)
    page.locator("main").get_by_role("link", name=re.compile(rf"^{tile}:")).click()
    expect(page).to_have_url(re.compile(rf"{board}\?{re.escape(query)}$"))
    if label:
        # The Status filter is a multi-select whose trigger shows the selection.
        expect(page.get_by_role("button", name="Status", exact=True)).to_have_text(label)
    chips = page.get_by_role("group", name="From dashboard")
    if chip:
        expect(chips.get_by_text(chip, exact=True)).to_be_visible()
    else:
        expect(chips).to_have_count(0)


@pytest.mark.parametrize(("role", "path", "board"), DASHBOARDS[:2])
def test_view_all_check_ins_opens_the_checked_in_board(as_role, role: str, path: str, board: str) -> None:
    page = _open_dashboard(as_role, role, path)
    page.get_by_role("link", name="View all checked-in and checked-out visitors").click()
    expect(page).to_have_url(re.compile(rf"{board}\?status=checked_in&status=checked_out$"))


def test_unknown_status_deep_link_is_ignored(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/invitations?status=bogus")
    expect(page.get_by_role("button", name="Status", exact=True)).to_have_text("All statuses")


@pytest.mark.parametrize(("role", "path", "board"), DASHBOARDS)
def test_range_toggle_switches_the_trend_to_thirty_days(as_role, role: str, path: str, board: str) -> None:
    page = _open_dashboard(as_role, role, path)
    trend = page.locator("main section").filter(has=page.get_by_role("heading", name=re.compile("Visitor Traffic|My Visits$")))
    with page.expect_response(lambda response: "analytics" in response.url and "range=30d" in response.url):
        page.get_by_role("button", name="30 days").click()
    # Either the chart (with its 30-row hidden table) or its empty state.
    expect(trend.get_by_text(re.compile(r"last 30 days")).first).to_be_visible()
    table_rows = trend.locator(".sr-only table tbody tr")
    if table_rows.count():
        expect(table_rows).to_have_count(30)


def test_host_dashboard_matches_their_own_overview(as_role, api) -> None:
    """staff-home-dashboard: the tiles show the caller's relevantToMe
    figures, the same numbers the personal overview API returns."""
    expected = api.call("GET", "/api/v1/admin/dashboard/my-overview", "host", expect=200, branch=None)
    page = _open_dashboard(as_role, "host", "/staff/dashboard")
    for label, key in (("Inside Now", "insideNow"), ("Awaiting Approval", "openAwaitingApproval"), ("Upcoming", "upcoming")):
        tile = page.locator("main").get_by_role("link", name=re.compile(rf"^{label}:"))
        expect(tile).to_have_attribute("aria-label", re.compile(rf"^{label}: {expected[key]}\b"))


@pytest.mark.parametrize(("role", "path", "board"), DASHBOARDS)
@pytest.mark.parametrize(("width", "height"), [(360, 740), (768, 1024), (1440, 900)])
def test_dashboard_has_no_horizontal_scroll(as_role, role: str, path: str, board: str, width: int, height: int) -> None:
    """dashboard-insights "Dashboard Layout Adapts From Phone to Desktop".
    `main` clips horizontal overflow, so it is checked too: clipped content
    would be unreachable."""
    page = _open_dashboard(as_role, role, path)
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(300)  # let the charts re-measure
    overflow = page.evaluate(
        """() => {
            const doc = document.documentElement
            const main = document.querySelector('main')
            return {
              document: doc.scrollWidth - doc.clientWidth,
              main: main ? main.scrollWidth - main.clientWidth : 0,
            }
        }"""
    )
    assert overflow == {"document": 0, "main": 0}, overflow
