"""Live refresh (refresh-every-10s-and-remind-unread-bell): list pages pick
up new data on their own within the 10s interval, every admin and staff page
has the top-bar refresh control, and on a form page that control asks before
discarding unsaved edits."""

import json
import re

import pytest
from playwright.sync_api import Page, expect

from conftest import Api, run_tag


def create_department(api: Api, name: str) -> dict:
    return api.call(
        "POST",
        "/api/v1/departments",
        "admin",
        expect=201,
        json={"branchId": api.branches["MAIN"], "name": name, "code": name.split()[-1][:12]},
    )


def refresh_control(page: Page):
    return page.get_by_role("button", name="Refresh", exact=True)


def test_list_page_shows_new_data_without_user_action(as_role, api: Api) -> None:
    admin = as_role("admin")
    admin.goto("/admin/departments")
    expect(admin.get_by_role("heading", name="Departments").first).to_be_visible()

    # "000…" sorts first under the list's default name order.
    name = f"000 QA Live {run_tag()}"
    department = create_department(api, name)
    try:
        expect(admin.get_by_text(name)).to_be_visible(timeout=13_000)
    finally:
        api.call("DELETE", f"/api/v1/departments/{department['id']}", "admin")


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("admin", "/admin/reception-desks"),
        ("admin", "/admin/security-gates"),
        ("admin", "/admin/branches/new"),
        ("admin", "/admin/audit-trail"),
        ("reception", "/staff/visitors/new"),
    ],
)
def test_every_page_has_the_refresh_control(as_role, role: str, path: str) -> None:
    page = as_role(role)
    page.goto(path)
    expect(refresh_control(page)).to_be_visible()


def test_form_refresh_asks_before_discarding_edits(as_role, api: Api) -> None:
    name = f"000 QA Form {run_tag()}"
    department = create_department(api, name)
    try:
        admin = as_role("admin")
        admin.goto(f"/admin/departments/{department['id']}/edit")
        name_input = admin.get_by_label("Department Name")
        expect(name_input).to_have_value(name)
        expect(refresh_control(admin)).to_be_visible()

        # Untouched: refreshes straight away, no confirmation.
        refresh_control(admin).click()
        expect(admin.get_by_role("dialog", name="Discard unsaved changes?")).to_have_count(0)
        expect(name_input).to_have_value(name)

        name_input.fill(f"{name} edited")
        refresh_control(admin).click()
        dialog = admin.get_by_role("dialog", name="Discard unsaved changes?")
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Cancel").click()
        expect(dialog).to_be_hidden()
        expect(name_input).to_have_value(f"{name} edited")

        refresh_control(admin).click()
        admin.get_by_role("dialog", name="Discard unsaved changes?").get_by_role(
            "button", name="Discard and refresh"
        ).click()
        expect(admin.get_by_label("Department Name")).to_have_value(name)
    finally:
        api.call("DELETE", f"/api/v1/departments/{department['id']}", "admin")


# --- manual-only-refresh-indicator-and-topbar-clock -------------------------

# Records whether the refresh icon ever turns (a running Web Animation on
# its spin wrapper, or the reduced-motion `animate-spin` class), sampled
# every frame so a brief spin between two checks can't be missed.
WATCH_SPIN = """() => {
    const spin = document.querySelector('header button[aria-label^="Refresh"] [data-refresh-spin]');
    const turning = () => spin.getAnimations().length > 0 || spin.classList.contains('animate-spin');
    window.__spun = turning();
    const sample = () => {
        if (turning()) window.__spun = true;
        requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
}"""

# At rest and upright: nothing animating and no leftover rotation.
SPIN_AT_REST = """() => {
    const spin = document.querySelector('header button[aria-label^="Refresh"] [data-refresh-spin]');
    return spin.getAnimations().length === 0 && !spin.classList.contains('animate-spin')
        && ['none', 'matrix(1, 0, 0, 1, 0, 0)'].includes(getComputedStyle(spin).transform);
}"""


def test_top_bar_clock_shows_local_24_hour_time(as_role) -> None:
    admin = as_role("admin")
    admin.goto("/admin/dashboard")
    clock = admin.locator("header time")
    expect(clock).to_have_text(re.compile(r"^\d{2}:\d{2}:\d{2}$"))

    shown = clock.inner_text()
    browser_now = admin.evaluate(
        "() => { const d = new Date(); return [d.getHours(), d.getMinutes(), d.getSeconds()] }"
    )
    hours, minutes, seconds = (int(part) for part in shown.split(":"))
    drift = abs((hours * 3600 + minutes * 60 + seconds) - (browser_now[0] * 3600 + browser_now[1] * 60 + browser_now[2]))
    assert drift <= 2 or drift >= 86_398, (shown, browser_now)

    expect(clock).not_to_have_text(shown, timeout=2_500)
    expect(admin.locator("header")).not_to_contain_text("Updated")


def test_clock_hidden_on_phones(new_context, tokens) -> None:
    context = new_context(viewport={"width": 360, "height": 800})
    token = tokens["users"]["admin"]["token"]
    context.add_init_script(f"try {{ sessionStorage.setItem('token', {json.dumps(token)}) }} catch {{}}")
    page = context.new_page()
    page.goto("/admin/dashboard")
    # On phones refresh lives in the "More options" menu (audit-and-harden §7.6).
    more = page.get_by_role("button", name=re.compile(r"^More options"))
    expect(more).to_be_visible()
    more.click()
    expect(page.get_by_role("menuitem", name="Refresh")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("header time")).to_be_hidden()
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")


def test_refresh_icon_spins_only_for_manual_refresh(as_role) -> None:
    admin = as_role("admin")
    admin.goto("/admin/dashboard")
    expect(refresh_control(admin)).to_be_visible()
    admin.wait_for_timeout(1_000)

    # Longer than one 10s automatic refresh: the icon must stay still.
    admin.evaluate(WATCH_SPIN)
    admin.wait_for_timeout(12_000)
    assert admin.evaluate("() => window.__spun") is False, "the icon spun for a background refresh"

    # A manual refresh spins the icon, then lets it settle upright.
    admin.evaluate(WATCH_SPIN)
    refresh_control(admin).click()
    admin.wait_for_function("() => window.__spun === true", timeout=5_000)
    admin.wait_for_function(SPIN_AT_REST, timeout=15_000)


def test_refresh_icon_eases_in_and_settles_upright(as_role) -> None:
    """tidy-toasts-and-refresh-spin: the spin starts slower than full speed
    and, when the refresh ends mid-turn, finishes the turn instead of
    snapping back to 0deg."""
    admin = as_role("admin")
    admin.goto("/admin/dashboard")
    expect(refresh_control(admin)).to_be_visible()
    admin.wait_for_timeout(1_000)

    # Hold the dashboard's re-fetch so the spin is caught mid-flight.
    held = []
    admin.route("**/api/v1/admin/dashboard/**", lambda route: held.append(route))
    angles = admin.evaluate(
        """async () => {
            const spin = document.querySelector('header button[aria-label^="Refresh"] [data-refresh-spin]');
            const angle = () => {
                const t = getComputedStyle(spin).transform;
                if (t === 'none') return 0;
                const m = new DOMMatrixReadOnly(t);
                return (Math.atan2(m.b, m.a) * 180 / Math.PI + 360) % 360;
            };
            document.querySelector('header button[aria-label^="Refresh"]').click();
            const samples = [];
            const start = performance.now();
            while (performance.now() - start < 500) {
                await new Promise(requestAnimationFrame);
                samples.push([performance.now() - start, angle()]);
            }
            return samples;
        }"""
    )
    # Ease-in: the first 100ms covers far less than full speed would
    # (360deg / 800ms -> 45deg per 100ms).
    early = max(angle for elapsed, angle in angles if elapsed <= 100)
    assert early < 25, f"the spin started at full speed: {angles[:8]}"
    assert any(angle > 60 for _, angle in angles), "the icon never got going"

    for route in held:
        route.continue_()
    admin.unroute("**/api/v1/admin/dashboard/**")
    admin.wait_for_function(SPIN_AT_REST, timeout=15_000)


def test_refresh_icon_under_reduced_motion_spins_plainly(new_context, tokens) -> None:
    """Reduced motion: a constant spin while the refresh runs, upright the
    moment it ends, and no hover nudge."""
    context = new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    token = tokens["users"]["admin"]["token"]
    context.add_init_script(f"try {{ sessionStorage.setItem('token', {json.dumps(token)}) }} catch {{}}")
    admin = context.new_page()
    admin.goto("/admin/dashboard")
    expect(refresh_control(admin)).to_be_visible()

    refresh_control(admin).hover()
    nudge = refresh_control(admin).locator(".refresh-nudge")
    assert nudge.evaluate("el => getComputedStyle(el).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")

    admin.evaluate(WATCH_SPIN)
    refresh_control(admin).click()
    admin.wait_for_function("() => window.__spun === true", timeout=5_000)
    spin = refresh_control(admin).locator("[data-refresh-spin]")
    assert spin.evaluate("el => el.getAnimations().every((a) => a instanceof CSSAnimation)")
    admin.wait_for_function(SPIN_AT_REST, timeout=15_000)
