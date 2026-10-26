"""Toasts (tidy-toasts-and-refresh-spin): they sit bottom-right clear of the
top bar, at most three show at once with the rest queued, hovering one keeps
it, and a burst of foreground pushes folds into one "N new notifications"
summary that opens the bell.

Foreground pushes are simulated the way Firebase delivers them to an open
tab: a `message` event on `navigator.serviceWorker`. Action toasts come from
the admin login form against a mocked 401, so no real login attempt is used.
"""

import json

from playwright.sync_api import Page, expect

# Delivers each body as a separate foreground push, as Firebase's
# service-worker bridge does.
PUSH = """(bodies) => bodies.forEach((body) => navigator.serviceWorker.dispatchEvent(
    new MessageEvent('message', { data: {
        isFirebaseMessaging: true,
        messageType: 'push-received',
        notification: { title: 'Guestify', body },
        data: {},
    } })
))"""

LOGIN_ERROR = "Invalid email or password. Please try again."


def open_toasts(page: Page):
    return page.locator('.motion-toast[data-state="open"]')


def push(page: Page, *bodies: str) -> None:
    page.evaluate(PUSH, list(bodies))


def failing_login_page(page: Page, fake_clock: bool = False) -> Page:
    if fake_clock:
        page.clock.install()
    page.route(
        "**/auth/login",
        lambda route: route.fulfill(status=401, content_type="application/json", body=json.dumps({"detail": "Invalid credentials"})),
    )
    page.goto("/admin/login")
    page.get_by_label("Email").fill("nobody@example.com")
    page.get_by_role("textbox", name="Password").fill("wrong-password")
    return page


def submit_login(page: Page, times: int) -> None:
    for _ in range(times):
        page.get_by_role("button", name="Sign In", exact=True).click()
        expect(page.get_by_role("button", name="Sign In", exact=True)).to_be_enabled()


def test_toast_sits_bottom_right_clear_of_the_top_bar(as_role) -> None:
    reception = as_role("reception")
    reception.goto("/staff/invitations")
    bell = reception.locator('header button[aria-label^="Notifications"]')
    expect(bell).to_be_visible()

    push(reception, "QA toast placement")
    toast = open_toasts(reception).first
    expect(toast).to_contain_text("QA toast placement")

    box = toast.bounding_box()
    header = reception.locator("header").bounding_box()
    assert box and header
    assert box["y"] > header["y"] + header["height"], "the toast overlaps the top bar"
    assert box["y"] + box["height"] >= 900 - 32, "the toast is not anchored to the bottom edge"
    assert box["x"] + box["width"] >= 1440 - 32, "the toast is not anchored to the right edge"

    # The bell is uncovered and works while the toast is up.
    bell.click()
    expect(reception.get_by_text("Notifications", exact=True)).to_be_visible()


def test_toast_on_a_phone_spans_the_bottom(new_context, tokens) -> None:
    context = new_context(viewport={"width": 390, "height": 800})
    token = tokens["users"]["reception"]["token"]
    context.add_init_script(f"try {{ sessionStorage.setItem('token', {json.dumps(token)}) }} catch {{}}")
    page = context.new_page()
    page.goto("/staff/invitations")
    expect(page.locator('header button[aria-label^="Notifications"]')).to_be_visible()

    push(page, "QA phone toast")
    toast = open_toasts(page).first
    expect(toast).to_contain_text("QA phone toast")
    box = toast.bounding_box()
    header = page.locator("header").bounding_box()
    assert box and header
    assert box["y"] > header["y"] + header["height"]
    assert box["y"] + box["height"] >= 800 - 32
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")


def test_a_lone_push_shows_its_own_message(as_role) -> None:
    reception = as_role("reception")
    reception.goto("/staff/invitations")
    expect(reception.locator('header button[aria-label^="Notifications"]')).to_be_visible()

    push(reception, "QA lone push")
    expect(open_toasts(reception)).to_have_count(1)
    expect(open_toasts(reception).first).to_contain_text("QA lone push")
    expect(open_toasts(reception).first).not_to_contain_text("new notifications")


def test_a_push_burst_folds_into_one_summary_that_opens_the_bell(as_role) -> None:
    reception = as_role("reception")
    reception.goto("/staff/invitations")
    expect(reception.locator('header button[aria-label^="Notifications"]')).to_be_visible()

    push(reception, *(f"QA burst push {index}" for index in range(10)))
    expect(open_toasts(reception)).to_have_count(1)
    summary = open_toasts(reception).first
    expect(summary).to_contain_text("10 new notifications")

    # Another push updates the same toast in place.
    handle = summary.element_handle()
    push(reception, "QA burst push 10")
    expect(summary).to_contain_text("11 new notifications")
    assert handle.evaluate("el => el.isConnected"), "the summary re-entered instead of updating in place"

    reception.get_by_role("button", name="11 new notifications").click()
    expect(reception.locator('header button[aria-label^="Notifications"]')).to_have_attribute("aria-expanded", "true")
    expect(reception.get_by_text("Notifications", exact=True)).to_be_visible()
    expect(open_toasts(reception)).to_have_count(0)


def test_action_feedback_is_not_merged_into_the_push_summary(as_role) -> None:
    # Signed in: the push listener only runs for a staff session, so the
    # action toast comes from a failing manual refresh of the board, mocked
    # only once the board's own first load has settled.
    page = as_role("reception")
    page.goto("/staff/invitations", wait_until="networkidle")
    refresh = page.get_by_role("button", name="Refresh", exact=True)
    expect(refresh).to_be_enabled()
    page.route(
        "**/api/v1/invitations?*",
        # A 4xx: the conftest fails any journey that sees a 5xx.
        lambda route: route.fulfill(status=400, content_type="application/json", body=json.dumps({"message": "boom"})),
    )
    refresh.click()
    expect(open_toasts(page)).to_have_count(1)
    action_toast_text = open_toasts(page).first.inner_text()

    push(page, "QA mixed push 1", "QA mixed push 2", "QA mixed push 3")
    expect(open_toasts(page)).to_have_count(2)
    expect(open_toasts(page).filter(has_text=action_toast_text)).to_have_count(1)
    expect(open_toasts(page).filter(has_text="3 new notifications")).to_have_count(1)


def test_at_most_three_toasts_show_and_the_rest_wait(as_role) -> None:
    page = failing_login_page(as_role("anonymous"), fake_clock=True)
    submit_login(page, 4)
    expect(open_toasts(page)).to_have_count(3)

    # Dismissing one 3s in lets the queued fourth in.
    page.clock.run_for(3_000)
    expect(open_toasts(page)).to_have_count(3)
    open_toasts(page).first.get_by_role("button", name="Dismiss notification").click()
    # Off the stack, or the toast that slides under the pointer pauses.
    page.mouse.move(5, 5)
    page.clock.run_for(500)
    expect(open_toasts(page)).to_have_count(3)

    # Its 6s error duration started when it appeared (t=3s), not when it
    # was raised: the other two expire at 6s, it lasts until 9s.
    page.clock.run_for(3_000)
    expect(open_toasts(page)).to_have_count(1)
    page.clock.run_for(3_000)
    expect(open_toasts(page)).to_have_count(0)


def test_hovering_a_toast_keeps_it(as_role) -> None:
    page = failing_login_page(as_role("anonymous"), fake_clock=True)
    submit_login(page, 1)
    toast = open_toasts(page).first
    expect(toast).to_be_visible()

    page.clock.run_for(2_000)
    toast.hover()
    page.clock.run_for(10_000)
    expect(open_toasts(page)).to_have_count(1)

    # Leaving resumes the remaining ~4s of its 6s.
    page.mouse.move(5, 5)
    page.clock.run_for(3_000)
    expect(open_toasts(page)).to_have_count(1)
    page.clock.run_for(1_500)
    expect(open_toasts(page)).to_have_count(0)
