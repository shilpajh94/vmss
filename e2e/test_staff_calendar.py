"""Staff calendar (openspec change add-staff-calendar, spec staff-calendar):
every role reaches it from its sidebar, each role sees exactly the scope
the API applies, month/week/day navigation keeps its state in the URL,
events open the invitation detail, and the page fits a phone."""

import datetime
import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, expect

from conftest import run_tag

CALENDAR = "/api/v1/invitations/calendar"
# (role, landing page, calendar path, invitation board)
ROLES = [
    ("admin", "/admin/dashboard", "/admin/calendar", "/admin/invitations"),
    ("reception", "/reception/dashboard", "/staff/calendar", "/staff/invitations"),
    ("security", "/staff/dashboard", "/staff/calendar", "/staff/invitations"),
    ("host", "/staff/dashboard", "/staff/calendar", "/staff/invitations"),
]
EXPECTED_SCOPE = {"admin": "branch", "reception": "branch", "security": "branch", "host": "mine", "branchb": "branch"}


def _today() -> str:
    return str(datetime.date.today())


def _feed(api, role: str, day: str, *, branch: str | None = None) -> dict:
    return api.call("GET", CALENDAR, role, expect=200, branch=branch, params={"from": day, "to": day})


def _query(page: Page) -> dict[str, list[str]]:
    return parse_qs(urlparse(page.url).query)


def _scroll_day_until(page: Page, locator) -> None:
    """Today fills up with other runs' 10:00 visits, so a visit this test
    just created may be past Day view's first page of 20: scroll the page
    until it loads."""
    expect(page.locator("main ul li").first).to_be_visible()
    for _ in range(20):
        if locator.count():
            return
        page.evaluate("document.querySelector('main').scrollTop = document.querySelector('main').scrollHeight")
        page.wait_for_timeout(400)


def _period_title(page: Page):
    return page.locator("main").get_by_role("heading", level=2)


@pytest.mark.parametrize(("role", "landing", "calendar", "board"), ROLES)
def test_every_role_reaches_the_calendar_from_its_sidebar(as_role, role: str, landing: str, calendar: str, board: str) -> None:
    page = as_role(role)
    page.goto(landing)
    page.get_by_role("navigation").get_by_role("button", name="Calendar").click()

    expect(page).to_have_url(re.compile(rf"{calendar}(\?|$)"))
    expect(page.get_by_role("heading", level=1, name="Calendar")).to_be_visible()
    expect(page.get_by_role("navigation").get_by_role("button", name="Calendar")).to_have_attribute("aria-current", "page")
    subtitle = "Your visits" if EXPECTED_SCOPE[role] == "mine" else re.compile(r"^All visits at ")
    expect(page.locator("main header p")).to_have_text(subtitle)


@pytest.mark.parametrize("role", list(EXPECTED_SCOPE))
def test_each_role_gets_its_scope(api, role: str) -> None:
    assert _feed(api, role, _today())["scope"] == EXPECTED_SCOPE[role]


def test_branch_scope_follows_the_branch(api) -> None:
    """Reception and security at MAIN see a MAIN visit they have nothing to
    do with; the branch-B reception never does."""
    name = f"QA Calendar Branch {run_tag()}"
    created = api.create_invitation(name, role="admin")
    day = _today()

    for role in ("reception", "security", "admin"):
        assert created["id"] in {event["id"] for event in _feed(api, role, day)["events"]}, role
    assert created["id"] not in {event["id"] for event in _feed(api, "branchb", day)["events"]}
    # An unauthorized branch header is refused, not silently widened.
    api.call("GET", CALENDAR, "branchb", expect=403, branch="MAIN", params={"from": day, "to": day})


def test_host_calendar_never_shows_more_than_their_own_list(api) -> None:
    day = _today()
    feed_ids = {event["id"] for event in _feed(api, "host", day)["events"]}
    mine = api.call(
        "GET", "/api/v1/invitations", "host", expect=200, branch=None, params={"relevantToMe": "true", "pageSize": 100}
    )
    assert feed_ids <= {row["id"] for row in mine}


def test_month_navigation_and_reload_keep_the_view(as_role) -> None:
    page = as_role("reception")
    page.goto("/staff/calendar?view=month&date=2026-10-15")
    expect(_period_title(page)).to_have_text("October 2026")

    page.get_by_role("button", name="Next month").click()
    expect(_period_title(page)).to_have_text("November 2026")
    assert _query(page)["date"] == ["2026-11-01"]

    page.reload()
    expect(_period_title(page)).to_have_text("November 2026")


def test_week_view_starts_on_monday_across_a_month_end(as_role) -> None:
    page = as_role("reception")
    page.goto("/staff/calendar?view=week&date=2026-10-29")
    expect(_period_title(page)).to_have_text("26 Oct – 1 Nov 2026")
    page.get_by_role("button", name="Previous week").click()
    expect(_period_title(page)).to_have_text("19 Oct – 25 Oct 2026")


def test_more_link_opens_the_day_and_an_event_opens_its_detail(as_role, api) -> None:
    tag = run_tag()
    names = [f"QA Calendar {tag} {index}" for index in range(4)]
    for name in names:
        api.create_invitation(name, role="admin")
    day = _today()

    page = as_role("reception")
    page.goto(f"/staff/calendar?view=month&date={day}")
    # Today's cell ("19 Oct: 5 visits"); other days may overflow too.
    today = datetime.date.fromisoformat(day)
    cell = page.get_by_label(re.compile(rf"^{today.day} {today.strftime('%b')}\w*: \d+ visits?$"))
    cell.get_by_role("button", name=re.compile(r"^\+\d+ more$")).click()
    expect(page).to_have_url(re.compile(r"view=day"))
    assert _query(page)["date"] == [day]

    chip = page.get_by_role("button", name=re.compile(re.escape(names[0])))
    _scroll_day_until(page, chip)
    chip.click()
    expect(page).to_have_url(re.compile(r"/staff/invitations\?invitationId="))
    expect(page.get_by_role("dialog")).to_be_visible()

    page.go_back()
    expect(page).to_have_url(re.compile(r"/staff/calendar\?"))
    assert _query(page)["view"] == ["day"]
    assert _query(page)["date"] == [day]


def test_denied_filter_is_off_by_default_and_can_be_shown(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/calendar?view=week")
    denied = page.get_by_role("group", name="Show statuses").get_by_role("button", name="Denied")
    expect(denied).to_have_attribute("aria-pressed", "false")

    denied.click()
    expect(denied).to_have_attribute("aria-pressed", "true")
    assert "denied" in _query(page)["status"]


def test_phone_opens_day_view_without_horizontal_scroll(as_role) -> None:
    page = as_role("security")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/staff/calendar")
    expect(page.get_by_role("heading", level=1, name="Calendar")).to_be_visible()
    # Day view's title is the full weekday date, e.g. "Monday, 19 October 2026".
    expect(_period_title(page)).to_have_text(re.compile(r"^[A-Z][a-z]+day,? \d{1,2} [A-Z][a-z]+ \d{4}$"))
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


# --- add-calendar-colours-and-theme-modes: status fills ------------------------

_BG = "el => getComputedStyle(el).backgroundColor"
_SURFACE = {"rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"}


def test_month_events_are_filled_with_their_status_colour(as_role, api) -> None:
    """staff-calendar "Month cell shows status fills"."""
    name = f"QA Calendar Fill {run_tag()}"
    api.create_invitation(name, role="admin")
    page = as_role("admin")
    page.emulate_media(color_scheme="light")
    page.goto(f"/admin/calendar?view=day&date={_today()}")
    chip = page.get_by_role("button", name=re.compile(re.escape(name)))
    _scroll_day_until(page, chip)
    expect(chip).to_be_visible()
    # A freshly created invitation is Pending: an info-blue tint, not the plain surface.
    background = chip.evaluate(_BG)
    assert background not in _SURFACE, background
    pending_chip = (
        page.get_by_role("group", name="Show statuses").get_by_role("button", name="Pending").evaluate(_BG)
    )
    assert background == pending_chip, (background, pending_chip)


def test_busy_day_count_steps_up(as_role) -> None:
    """staff-calendar "Busy day stands out": the month's count badges carry
    stronger tints on busier days."""
    page = as_role("admin")
    page.emulate_media(color_scheme="light")
    page.goto(f"/admin/calendar?view=month&date={_today()}")
    badges = page.locator("main [title$=' visits'], main [title$=' visit']")
    expect(badges.first).to_be_visible()
    seen: dict[str, str] = {}
    for index in range(badges.count()):
        badge = badges.nth(index)
        total = int(badge.inner_text())
        step = "light" if total < 5 else "medium" if total < 15 else "strong"
        seen.setdefault(step, badge.evaluate(_BG))
    assert len(set(seen.values())) == len(seen), seen


def test_status_filled_events_in_dark_mode(as_role) -> None:
    page = as_role("admin")
    page.emulate_media(color_scheme="dark")
    page.goto(f"/admin/calendar?view=day&date={_today()}")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    chip = page.locator("main ul button").first
    expect(chip).to_be_visible()
    assert chip.evaluate(_BG) not in _SURFACE | {"rgb(15, 23, 42)"}
    assert chip.evaluate("el => getComputedStyle(el).color") == "rgb(241, 245, 249)"


# --- improve-calendar-scale-and-theme-switch: scrolling day columns ------------

BUSY_DAY = "2026-10-19"  # the QA tenant's busy Monday (100+ visits at MAIN)
QUIET_DAY = "2026-10-21"
WEEK_URL = f"/staff/calendar?view=week&date={BUSY_DAY}"


def _day_total(api, day: str) -> int:
    return _feed(api, "reception", day)["days"][0]["total"]


def _column(page: Page, day: str):
    label = datetime.date.fromisoformat(day)
    return page.locator(f"section[aria-label^='{label.day} {label.strftime('%b')}']").first


def _scroll_column_to_end(column) -> None:
    column.locator("div.overflow-y-auto").first.evaluate("el => { el.scrollTop = el.scrollHeight }")


def _settled_count(column) -> int:
    """Loaded visits once loading stops. A column preloads the next page
    while its last card is within 200px of the bottom, so with two-line
    cards a tall column settles at 20, not 10 (staff-calendar: "at least
    10")."""
    expect(column.locator("li").first).to_be_attached()
    expect(column.get_by_text("Loading more…")).to_have_count(0)
    column.page.wait_for_timeout(300)
    expect(column.get_by_text("Loading more…")).to_have_count(0)
    return column.locator("li").count()


def test_busy_day_scrolls_inside_its_column(as_role, api) -> None:
    total = _day_total(api, BUSY_DAY)
    assert total > 40, f"QA data needs a busy {BUSY_DAY}; found {total}"
    page = as_role("reception")
    page.goto(WEEK_URL)
    monday = _column(page, BUSY_DAY)
    loaded = _settled_count(monday)
    assert 10 <= loaded < total, loaded
    expect(monday.get_by_text(f"Showing {loaded} of {total}")).to_be_attached()
    # The page itself doesn't grow with the visits.
    overflow = page.evaluate("(() => { const m = document.querySelector('main'); return m.scrollHeight - m.clientHeight })()")
    assert overflow == 0, overflow
    expect(page.get_by_text("Not every visit in this range is listed")).to_have_count(0)


def test_scrolling_a_column_loads_more_until_the_whole_day(as_role, api) -> None:
    total = _day_total(api, BUSY_DAY)
    page = as_role("reception")
    page.goto(WEEK_URL)
    monday = _column(page, BUSY_DAY)
    other = _column(page, QUIET_DAY)
    first = _settled_count(monday)
    other_before = other.locator("li").count()

    _scroll_column_to_end(monday)
    expect(monday.locator("li")).not_to_have_count(first)
    loaded = _settled_count(monday)
    expect(monday.get_by_text(f"Showing {loaded} of {total}")).to_be_attached()
    assert other.locator("li").count() == other_before

    for _ in range(total // 10 + 2):
        if monday.locator("li").count() >= total:
            break
        loaded = monday.locator("li").count()
        _scroll_column_to_end(monday)
        expect(monday.locator("li")).not_to_have_count(loaded)
    expect(monday.locator("li")).to_have_count(total)
    expect(monday.get_by_text(f"All {total} visits")).to_be_visible()


def test_refresh_keeps_loaded_visits_and_scroll_position(as_role) -> None:
    page = as_role("reception")
    page.goto(WEEK_URL)
    monday = _column(page, BUSY_DAY)
    for _ in range(2):
        loaded = _settled_count(monday)
        _scroll_column_to_end(monday)
        expect(monday.locator("li")).not_to_have_count(loaded)
    loaded = _settled_count(monday)
    body = monday.locator("div.overflow-y-auto").first
    body.evaluate("el => { el.scrollTop = 600 }")
    page.get_by_role("button", name=re.compile(r"^Refresh")).click()
    page.wait_for_timeout(1500)
    expect(monday.locator("li")).to_have_count(loaded)
    assert abs(body.evaluate("el => el.scrollTop") - 600) <= 2


def test_status_filter_resets_columns(as_role) -> None:
    page = as_role("reception")
    page.goto(WEEK_URL)
    monday = _column(page, BUSY_DAY)
    first = _settled_count(monday)
    for _ in range(2):
        loaded = _settled_count(monday)
        _scroll_column_to_end(monday)
        expect(monday.locator("li")).not_to_have_count(loaded)
    deep = _settled_count(monday)
    assert deep > first, (first, deep)
    page.get_by_role("group", name="Show statuses").get_by_role("button", name="Visited").click()
    # Back to the first page (plus the preload a tall column always makes).
    expect(monday.locator("li")).not_to_have_count(deep)
    assert _settled_count(monday) <= first


def test_day_view_pages_by_twenty(as_role, api) -> None:
    total = _day_total(api, BUSY_DAY)
    page = as_role("reception")
    page.goto(f"/staff/calendar?view=day&date={BUSY_DAY}")
    items = page.locator("main ul li")
    expect(items).to_have_count(20)
    page.evaluate("document.querySelector('main').scrollTop = document.querySelector('main').scrollHeight")
    expect(items).to_have_count(min(40, total))
    expect(page.get_by_text(f"Showing {min(40, total)} of {total}")).to_be_visible()


def test_week_columns_per_screen(as_role) -> None:
    for width, per_screen in ((390, 1), (820, 3), (1440, 5), (1920, 7)):
        page = as_role("reception")
        page.set_viewport_size({"width": width, "height": 844})
        page.goto(WEEK_URL)
        monday = _column(page, BUSY_DAY)
        expect(monday).to_be_visible()
        board = page.locator("main div.snap-x").first
        ratio = board.evaluate("el => el.clientWidth") / monday.evaluate("el => el.getBoundingClientRect().width")
        assert round(ratio) == per_screen, (width, ratio)
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow == 0, (width, overflow)
        page.context.close()


# --- fix-page-bottom-gap-and-full-day-calendar: full-day timeline --------------

TIMELINE_DAY = "2026-12-02"  # a quiet Wednesday the tests below seed
EMPTY_DAY = "2027-02-17"
HOUR_LABELS = [f"{(hour % 12) or 12}:00 {'AM' if hour < 12 else 'PM'}" for hour in range(24)]
WORKING_HOURS = HOUR_LABELS[9:19]  # 9:00 AM to 6:00 PM
STATUS_WORDS = ("Pending", "Expected", "Inside", "Visited", "Missed", "Denied")
# Every hour heading's label, in order; Intl puts a narrow no-break space
# before AM/PM.
SLOT_LABELS = """root => [...root.querySelectorAll('section[aria-label]')]
  .map(section => section.getAttribute('aria-label').replace(/\\u202f/g, ' '))
  .filter(label => /^\\d{1,2}:00 [AP]M$|^Any time$/.test(label))"""


def _hour_section(root, label: str):
    return root.locator("section[aria-label]").filter(
        has=root.page.locator("h3", has_text=re.compile(rf"^{re.escape(label).replace(chr(92) + ' ', '.')}$"))
    )


def _assert_timeline(labels: list[str], extra_hours: set[int]) -> None:
    """staff-calendar "Working-hours timeline": 9:00 AM–6:00 PM always,
    other hours only with visits, "Any time" last."""
    hours = sorted(set(range(9, 19)) | extra_hours)
    timed = [label for label in labels if label != "Any time"]
    assert timed == [HOUR_LABELS[hour] for hour in hours], labels
    assert labels[len(timed):] in ([], ["Any time"]), labels


@pytest.fixture(scope="module")
def timeline_visits(api) -> tuple[str, str]:
    tag = run_tag()
    early, late = f"QA Calendar Early {tag}", f"QA Calendar Late {tag}"
    api.create_invitation(early, role="admin", day=TIMELINE_DAY, time="00:30:00")
    api.create_invitation(late, role="admin", day=TIMELINE_DAY, time="23:15:00")
    return early, late


def test_day_view_shows_working_hours_and_busy_out_of_hours(as_role, timeline_visits) -> None:
    early, late = timeline_visits
    page = as_role("reception")
    page.goto(f"/staff/calendar?view=day&date={TIMELINE_DAY}")
    expect(page.get_by_role("button", name=re.compile(re.escape(late)))).to_be_visible()
    _assert_timeline(page.locator("main").evaluate(SLOT_LABELS), {0, 23})
    main = page.locator("main")
    expect(_hour_section(main, "12:00 AM").get_by_role("button", name=re.compile(re.escape(early)))).to_have_count(1)
    expect(_hour_section(main, "11:00 PM").get_by_role("button", name=re.compile(re.escape(late)))).to_have_count(1)


def test_week_column_shows_working_hours_and_busy_out_of_hours(as_role, timeline_visits) -> None:
    early, late = timeline_visits
    page = as_role("reception")
    page.goto(f"/staff/calendar?view=week&date={TIMELINE_DAY}")
    column = _column(page, TIMELINE_DAY)
    expect(column.get_by_role("button", name=re.compile(re.escape(late)))).to_be_attached()
    _assert_timeline(column.evaluate(SLOT_LABELS), {0, 23})
    expect(_hour_section(column, "12:00 AM").get_by_role("button", name=re.compile(re.escape(early)))).to_have_count(1)
    expect(_hour_section(column, "11:00 PM").get_by_role("button", name=re.compile(re.escape(late)))).to_have_count(1)


def test_empty_day_shows_no_visits_and_working_hours(as_role, api) -> None:
    if _day_total(api, EMPTY_DAY):
        pytest.skip(f"{EMPTY_DAY} is expected to have no visits")
    page = as_role("reception")
    page.goto(f"/staff/calendar?view=week&date={EMPTY_DAY}")
    column = _column(page, EMPTY_DAY)
    expect(column.get_by_text("No visits", exact=True)).to_be_attached()
    assert column.evaluate(SLOT_LABELS) == WORKING_HOURS


def test_column_opens_at_its_top(as_role) -> None:
    page = as_role("reception")
    page.goto(WEEK_URL)
    monday = _column(page, BUSY_DAY)
    _settled_count(monday)
    body = monday.locator("div.overflow-y-auto").first
    assert body.evaluate("el => el.scrollTop") == 0
    assert monday.evaluate(SLOT_LABELS)[0] in (HOUR_LABELS[:9] + ["9:00 AM"])


def test_unloaded_hours_sit_below_the_progress_row(as_role, api) -> None:
    total = _day_total(api, BUSY_DAY)
    page = as_role("reception")
    page.goto(WEEK_URL)
    monday = _column(page, BUSY_DAY)
    loaded = _settled_count(monday)
    progress = monday.get_by_text(f"Showing {loaded} of {total}")
    expect(progress).to_be_attached()
    last_working_hour = _hour_section(monday, "6:00 PM")
    assert progress.evaluate("el => el.getBoundingClientRect().top") < last_working_hour.evaluate(
        "el => el.getBoundingClientRect().top"
    )


def test_week_cards_show_status_by_colour_not_word(as_role) -> None:
    """staff-calendar "Two-line week card": no visible status word, but the
    accessible name still carries it."""
    page = as_role("reception")
    page.goto(WEEK_URL)
    card = _column(page, BUSY_DAY).locator("li button").first
    expect(card).to_be_attached()
    name = card.get_attribute("aria-label") or ""
    assert any(word in name for word in STATUS_WORDS), name
    text = card.inner_text()
    assert not any(word in text for word in STATUS_WORDS), text
    assert len([line for line in text.splitlines() if line.strip()]) <= 2, text


def test_current_week_opens_at_today(as_role) -> None:
    page = as_role("reception")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto("/staff/calendar?view=week")
    today = page.locator("main section[data-today]")
    expect(today).to_be_attached()
    board = page.locator("main div.snap-x").first
    box, column = board.bounding_box(), today.bounding_box()
    assert box and column
    assert column["x"] >= box["x"] - 1 and column["x"] + column["width"] <= box["x"] + box["width"] + 1, (box, column)


def test_week_board_leaves_the_page_gap_without_scrolling_the_page(as_role) -> None:
    """app-shell "Calendar week board fits without scrolling the page"."""
    page = as_role("reception")
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(WEEK_URL)
    expect(_column(page, BUSY_DAY).locator("li")).to_have_count(10)
    result = page.evaluate(
        """() => {
            const main = document.querySelector('main')
            const board = main.querySelector('div.snap-x')
            const mainBottom = main.getBoundingClientRect().top + main.clientHeight
            return {
              overflow: main.scrollHeight - main.clientHeight,
              gap: Math.round(mainBottom - board.getBoundingClientRect().bottom),
            }
        }"""
    )
    assert result == {"overflow": 0, "gap": 32}, result
    expect(page.get_by_role("heading", level=1, name="Calendar")).to_be_in_viewport(ratio=1)
