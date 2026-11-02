"""Device matrix (openspec change improve-calendar-scale-and-theme-switch,
app-shell "Staff and admin pages fit every supported device width"): every
staff and admin route at each supported width, light and dark — no
horizontal page scroll, no main content wider than main (it clips, so that
content would be unreachable), a one-row top bar, and (change
fix-page-bottom-gap-and-full-day-calendar) the page padding left below the
last element when main is scrolled to the end; (change
fix-paging-footers-and-calendar-day-scroll) paged lists keep their
pagination in view. The route sweep is slow (~620 page loads):
run with the full e2e pass or for any layout change."""

import json

import pytest
from playwright.sync_api import Page

WIDTHS = [320, 360, 390, 414, 768, 820, 1024, 1280, 1440, 1920]
ADMIN_ROUTES = [
    "/admin/dashboard", "/admin/organisation-configs", "/admin/branches", "/admin/branches/new",
    "/admin/departments", "/admin/departments/new", "/admin/buildings", "/admin/buildings/new",
    "/admin/floors", "/admin/floors/new", "/admin/host-employees", "/admin/host-employees/new",
    "/admin/reception-desks", "/admin/security-gates", "/admin/kiosks", "/admin/kiosks/new",
    "/admin/visitor-categories", "/admin/visitor-categories/new", "/admin/workflows", "/admin/workflows/new",
    "/admin/invitations", "/admin/calendar?view=month", "/admin/calendar?view=week", "/admin/calendar?view=day",
    "/admin/roles", "/admin/roles/new", "/admin/form-builder", "/admin/audit-trail",
]
STAFF_ROUTES = [
    ("reception", "/reception/dashboard"), ("reception", "/staff/invitations"),
    ("reception", "/staff/calendar?view=month"), ("reception", "/staff/calendar?view=week"),
    ("reception", "/staff/calendar?view=day"), ("reception", "/staff/visitors/new"),
    ("host", "/staff/dashboard"),
]
ROUTES = [("admin", route) for route in ADMIN_ROUTES] + STAFF_ROUTES

MEASURE = """() => {
  const doc = document.documentElement, main = document.querySelector('main'), header = document.querySelector('header')
  const result = {
    document: doc.scrollWidth - doc.clientWidth,
    main: main ? main.scrollWidth - main.clientWidth : 0,
    header: header ? Math.round(header.getBoundingClientRect().height) : 0,
    mainScroll: 0,
    endGap: null,
    padding: 0,
  }
  const wrapper = main?.firstElementChild
  if (!main || !wrapper) return result
  // app-shell "Page content keeps a bottom gap": scrolled to the end, the
  // last element (not the trailing aria-hidden spacer) ends at least the
  // page padding above main's bottom edge.
  result.mainScroll = main.scrollHeight - main.clientHeight
  main.scrollTop = main.scrollHeight
  const content = [...wrapper.children].filter(el => el.getAttribute('aria-hidden') !== 'true')
  const bottom = Math.max(...content.map(el => el.getBoundingClientRect().bottom))
  result.endGap = Math.round(main.getBoundingClientRect().top + main.clientHeight - bottom)
  result.padding = parseFloat(getComputedStyle(main).paddingLeft)
  return result
}"""


@pytest.mark.slow
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", WIDTHS)
def test_every_route_fits(as_role, width: int, theme: str) -> None:
    failures: list[str] = []
    pages: dict[str, Page] = {}
    for role, route in ROUTES:
        page = pages.get(role)
        if page is None:
            page = as_role(role)
            page.context.add_init_script(
                f"try {{ localStorage.setItem('vmss.themeMode', {json.dumps(json.dumps(theme))}) }} catch {{}}"
            )
            page.set_viewport_size({"width": width, "height": 800})
            pages[role] = page
        page.goto(route)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(250)
        result = page.evaluate(MEASURE)
        # The week board and day card are as tall as the visible page, so the
        # page scrolls on Week and Day too (calendar-page-scroll-and-taller-panels).
        gap_short = result["endGap"] is not None and result["endGap"] < result["padding"] - 1
        if result["document"] > 0 or result["main"] > 0 or result["header"] > 72 or gap_short:
            failures.append(f"{route}: {result}")
    assert not failures, f"{width}px {theme}:\n" + "\n".join(failures)


PAGED_LISTS = [
    "/admin/branches", "/admin/buildings", "/admin/floors", "/admin/departments", "/admin/roles",
    "/admin/host-employees", "/admin/visitor-categories", "/admin/kiosks", "/admin/workflows",
    "/admin/audit-trail",
]

PAGINATION = """() => {
  const main = document.querySelector('main')
  const text = [...main.querySelectorAll('p')].find(p => /^Showing \\d+-\\d+ of \\d+/.test(p.textContent || ''))
  if (!text) return null
  const inView = el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight }
  return {
    mainScroll: main.scrollHeight - main.clientHeight,
    text: inView(text),
    prev: inView(main.querySelector('[aria-label="Previous page"]')),
    next: inView(main.querySelector('[aria-label="Next page"]')),
  }
}"""


@pytest.mark.parametrize(("width", "height"), [(1280, 720), (1440, 900)])
def test_paged_list_pagination_stays_visible(as_role, width: int, height: int) -> None:
    """responsive-layout "Paged List Pagination Stays Visible Below the Data":
    on every paged list that has rows, the pagination is in the window and
    the page itself doesn't scroll."""
    page = as_role("admin")
    page.set_viewport_size({"width": width, "height": height})
    failures: list[str] = []
    for route in PAGED_LISTS:
        page.goto(route)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(250)
        result = page.evaluate(PAGINATION)
        if result is None:  # an empty list has no pagination
            continue
        if result != {"mainScroll": 0, "text": True, "prev": True, "next": True}:
            failures.append(f"{route}: {result}")
    assert not failures, f"{width}x{height}:\n" + "\n".join(failures)


# The split-screen layout's footer, at the bottom of the content panel
# (responsive-layout "The Public Portal Footer Is Compact").
FOOTER = """() => {
  const footer = document.querySelector('main footer')
  const style = getComputedStyle(footer)
  const centre = el => { const r = el.getBoundingClientRect(); return r.top + r.height / 2 }
  const links = [...footer.querySelectorAll('a')].filter(a => a.offsetParent !== null)
  return {
    height: footer.getBoundingClientRect().height,
    paddingTop: parseFloat(style.paddingTop),
    paddingBottom: parseFloat(style.paddingBottom),
    centres: links.map(centre),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }
}"""


def test_public_footer_is_compact(as_role) -> None:
    page = as_role("anonymous")
    page.goto("/visitor/track")
    page.locator("main footer").wait_for(state="attached")
    desktop = page.evaluate(FOOTER)
    assert desktop["height"] <= 88, desktop
    # The configured links sit on one row from `lg` up.
    if desktop["centres"]:
        assert max(desktop["centres"]) - min(desktop["centres"]) <= 4, desktop

    page.set_viewport_size({"width": 360, "height": 740})
    phone = page.evaluate(FOOTER)
    assert phone["paddingTop"] <= 16 and phone["paddingBottom"] <= 16, phone
    assert phone["overflow"] == 0, phone
