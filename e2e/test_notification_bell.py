"""The top-bar notification bell (show-exact-unread-count-and-ring-bell):
the badge always shows the exact unread count, "0" included, and the bell
rings when a refresh brings in a notification it hadn't seen - but not on
the first load after sign-in."""

import re

from playwright.sync_api import Page, expect

from conftest import Api, run_tag, wait_for


def unread_count(api: Api) -> int:
    return api.call("GET", "/api/v1/notifications/unread-count", "reception", expect=200)["unreadCount"]


def bell(page: Page, count: int):
    return page.get_by_role("button", name=f"Notifications, {count} unread")


def bell_icon(page: Page, count: int):
    # The first span inside the button wraps the icon and carries the ring.
    return bell(page, count).locator("span").first


def test_bell_shows_exact_count_and_rings_on_new_arrivals(as_role, api: Api) -> None:
    api.call("POST", "/api/v1/notifications/read-all", "reception", expect=200)

    reception = as_role("reception")
    reception.goto("/staff/invitations")
    expect(bell(reception, 0)).to_be_visible()
    expect(bell(reception, 0)).to_contain_text("0")
    expect(bell_icon(reception, 0)).not_to_have_class(re.compile("motion-bell-ring"))

    # Each submitted QA_SINGLE request notifies every Reception holder at
    # the branch, so eleven of them make the count go past the old "9+" cap.
    tag = run_tag()
    for index in range(11):
        api.create_invitation(f"QA E2E Bell {tag} {index}", role="host", category="QA_SINGLE")
    wait_for(lambda: unread_count(api), 11, timeout=30.0)

    # A visible tab refetches on visibilitychange, as it does on the poll.
    reception.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    expect(bell(reception, 11)).to_contain_text("11")
    expect(bell(reception, 11)).not_to_contain_text("9+")
    expect(bell_icon(reception, 11)).to_have_class(re.compile("motion-bell-ring"))

    # A fresh load is the session's first: count shown, no ring.
    reception.reload()
    expect(bell(reception, 11)).to_be_visible()
    expect(bell_icon(reception, 11)).not_to_have_class(re.compile("motion-bell-ring"))

    reception.get_by_role("button", name="Notifications, 11 unread").click()
    reception.get_by_role("button", name="Mark all read").click()
    expect(bell(reception, 0)).to_contain_text("0")


def test_bell_reminds_every_15_seconds_while_unread(as_role, api: Api) -> None:
    """refresh-every-10s-and-remind-unread-bell: while anything is unread the
    bell rings again every 15s; once everything is read it stops. A fake
    clock fast-forwards the timers instead of waiting in real time."""
    api.call("POST", "/api/v1/notifications/read-all", "reception", expect=200)
    api.create_invitation(f"QA E2E Bell Reminder {run_tag()}", role="host", category="QA_SINGLE")
    wait_for(lambda: unread_count(api), 1, timeout=30.0)

    reception = as_role("reception")
    reception.clock.install()
    reception.goto("/staff/invitations")
    icon = bell_icon(reception, 1)
    expect(icon).not_to_have_class(re.compile("motion-bell-ring"))

    reception.clock.run_for(16_000)
    first_ring = bell_icon(reception, 1)
    expect(first_ring).to_have_class(re.compile("motion-bell-ring"))
    first_ring_handle = first_ring.element_handle()

    # The next reminder remounts the icon wrapper to replay the ring.
    reception.clock.run_for(16_000)
    expect(bell_icon(reception, 1)).to_have_class(re.compile("motion-bell-ring"))
    assert not first_ring_handle.evaluate("el => el.isConnected")

    reception.get_by_role("button", name="Notifications, 1 unread").click()
    reception.get_by_role("button", name="Mark all read").click()
    reception.keyboard.press("Escape")
    reception.mouse.click(5, 5)
    expect(bell(reception, 0)).to_be_visible()
    settled_handle = bell_icon(reception, 0).element_handle()
    reception.clock.run_for(20_000)
    assert settled_handle.evaluate("el => el.isConnected"), "the bell rang again with nothing unread"


def test_bell_never_animates_with_nothing_unread(as_role, api: Api) -> None:
    """remind-unread-bell-every-15s: a refresh that brings in a notification
    the bell hasn't seen, but which is already read, must not ring."""
    api.call("POST", "/api/v1/notifications/read-all", "reception", expect=200)
    reception = as_role("reception")
    reception.goto("/staff/invitations")
    expect(bell(reception, 0)).to_be_visible()
    still_icon = bell_icon(reception, 0).element_handle()

    api.create_invitation(f"QA E2E Bell Read {run_tag()}", role="host", category="QA_SINGLE")
    wait_for(lambda: unread_count(api), 1, timeout=30.0)
    api.call("POST", "/api/v1/notifications/read-all", "reception", expect=200)

    with reception.expect_response(lambda r: "/api/v1/notifications/unread-count" in r.url):
        reception.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    reception.wait_for_timeout(500)
    expect(bell(reception, 0)).to_be_visible()
    assert still_icon.evaluate("el => el.isConnected"), "the bell animated with nothing unread"
