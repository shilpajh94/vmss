"""Theme modes (openspec change add-calendar-colours-and-theme-modes, spec
theme-mode): the Light/Dark/System control on staff and admin pages, System
following the device, the choice surviving a reload, no flash of the wrong
theme, and public pages staying light."""

import json
import re

from playwright.sync_api import Page, expect

STORAGE_KEY = "vmss.themeMode"
THEME_BUTTON = re.compile(r"^Theme: ")


def _store_mode(page: Page, mode: str) -> None:
    page.context.add_init_script(f"try {{ localStorage.setItem({json.dumps(STORAGE_KEY)}, {json.dumps(json.dumps(mode))}) }} catch {{}}")


def _html(page: Page):
    return page.locator("html")


def _wait_for_shell(page: Page) -> None:
    expect(page.get_by_role("button", name=THEME_BUTTON)).to_be_visible()


def test_control_is_on_staff_and_admin_pages(as_role) -> None:
    for role, path in (("host", "/staff/calendar"), ("admin", "/admin/branches")):
        page = as_role(role)
        page.goto(path)
        expect(page.get_by_role("button", name=THEME_BUTTON)).to_be_visible()


def test_choosing_dark_applies_at_once_and_survives_a_reload(as_role) -> None:
    page = as_role("reception")
    page.emulate_media(color_scheme="light")
    page.goto("/reception/dashboard")
    _wait_for_shell(page)
    expect(_html(page)).not_to_have_attribute("data-theme", "dark")

    page.get_by_role("button", name=THEME_BUTTON).click()
    page.get_by_role("menuitemradio", name="Dark").click()
    expect(_html(page)).to_have_attribute("data-theme", "dark")
    expect(page.get_by_role("button", name="Theme: Dark")).to_be_visible()
    surface = page.evaluate("getComputedStyle(document.querySelector('header')).backgroundColor")
    assert surface == "rgb(15, 23, 42)", surface

    page.reload()
    _wait_for_shell(page)
    expect(_html(page)).to_have_attribute("data-theme", "dark")
    page.get_by_role("button", name="Theme: Dark").click()
    expect(page.get_by_role("menuitemradio", name="Dark")).to_have_attribute("aria-checked", "true")


def test_system_follows_the_device_live(as_role) -> None:
    page = as_role("security")
    page.emulate_media(color_scheme="dark")
    page.goto("/staff/dashboard")
    _wait_for_shell(page)
    expect(page.get_by_role("button", name="Theme: System")).to_be_visible()
    expect(_html(page)).to_have_attribute("data-theme", "dark")

    page.emulate_media(color_scheme="light")
    expect(_html(page)).not_to_have_attribute("data-theme", "dark")
    page.emulate_media(color_scheme="dark")
    expect(_html(page)).to_have_attribute("data-theme", "dark")


def test_explicit_light_ignores_a_dark_device(as_role) -> None:
    page = as_role("host")
    _store_mode(page, "light")
    page.emulate_media(color_scheme="dark")
    page.goto("/staff/calendar")
    _wait_for_shell(page)
    expect(_html(page)).not_to_have_attribute("data-theme", "dark")


def test_dark_is_applied_before_the_app_runs(as_role) -> None:
    """No flash: the theme is on <html> when parsing finishes, before the
    deferred app bundle has run."""
    page = as_role("admin")
    _store_mode(page, "dark")
    page.context.add_init_script(
        """document.addEventListener('readystatechange', () => {
             if (document.readyState === 'interactive' && window.__firstTheme === undefined)
               window.__firstTheme = document.documentElement.getAttribute('data-theme')
           })"""
    )
    page.goto("/admin/dashboard")
    _wait_for_shell(page)
    assert page.evaluate("window.__firstTheme") == "dark"


def test_public_pages_stay_light(as_role) -> None:
    page = as_role("reception")
    _store_mode(page, "dark")
    page.emulate_media(color_scheme="dark")
    page.goto("/staff/calendar")
    _wait_for_shell(page)
    expect(_html(page)).to_have_attribute("data-theme", "dark")

    for path in ("/staff/login", "/admin/login", "/"):
        page.goto(path)
        page.wait_for_load_state("networkidle")
        expect(_html(page)).not_to_have_attribute("data-theme", "dark")


def test_blocked_storage_falls_back_to_system(as_role) -> None:
    page = as_role("host")
    page.context.add_init_script(
        "Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new Error('blocked') } })"
    )
    page.emulate_media(color_scheme="dark")
    page.goto("/staff/dashboard")
    _wait_for_shell(page)
    expect(page.get_by_role("button", name="Theme: System")).to_be_visible()
    expect(_html(page)).to_have_attribute("data-theme", "dark")


def test_menu_is_keyboard_operable(as_role) -> None:
    page = as_role("admin")
    page.emulate_media(color_scheme="light")
    page.goto("/admin/dashboard")
    button = page.get_by_role("button", name=THEME_BUTTON)
    button.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("menuitemradio", name="System")).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(page.get_by_role("menuitemradio", name="Dark")).to_be_focused()
    page.keyboard.press("Enter")
    expect(_html(page)).to_have_attribute("data-theme", "dark")
    expect(page.get_by_role("menu")).to_have_count(0)
    expect(page.get_by_role("button", name="Theme: Dark")).to_be_focused()

    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    expect(page.get_by_role("menu")).to_have_count(0)
    expect(_html(page)).to_have_attribute("data-theme", "dark")


def test_phone_top_bar_keeps_the_control_on_one_row(as_role) -> None:
    page = as_role("reception")
    page.set_viewport_size({"width": 360, "height": 740})
    page.goto("/staff/calendar")
    _wait_for_shell(page)
    header = page.locator("header").first
    theme = page.get_by_role("button", name=THEME_BUTTON)
    header_box, theme_box = header.bounding_box(), theme.bounding_box()
    assert header_box and theme_box
    assert header_box["height"] <= 72, header_box
    assert theme_box["x"] + theme_box["width"] <= header_box["x"] + header_box["width"] + 0.5
    overflow = page.evaluate("(() => { const h = document.querySelector('header'); return h.scrollWidth - h.clientWidth })()")
    assert overflow == 0, overflow


# --- improve-calendar-scale-and-theme-switch: one clean repaint ---------------

# Clicks Dark in the open theme menu, then samples frame by frame: in the
# first frame where the top bar is dark, are the chart ticks dark too, are
# transitions suspended, and is the menu already gone?
_SWITCH_AND_SAMPLE = """async () => {
  const item = [...document.querySelectorAll('[role=menuitemradio]')].find(el => el.textContent.trim() === 'Dark')
  item.click()
  const menuGoneAtClick = document.querySelector('[role=menu]') === null
  const header = document.querySelector('header')
  for (let frame = 0; frame < 120; frame++) {
    await new Promise(requestAnimationFrame)
    if (getComputedStyle(header).backgroundColor !== 'rgb(15, 23, 42)') continue
    const tick = document.querySelector('.recharts-cartesian-axis-tick-value')
    const pressable = document.querySelector('[class*="transition-colors"]')
    return {
      frame,
      menuGoneAtClick,
      tickFill: tick ? tick.getAttribute('fill') : null,
      switching: document.documentElement.hasAttribute('data-theme-switching'),
      pressTransition: pressable ? getComputedStyle(pressable).transitionDuration : null,
    }
  }
  return null
}"""


def _open_dashboard_light(as_role, reduced_motion: str = "no-preference") -> Page:
    page = as_role("admin")
    page.emulate_media(color_scheme="light", reduced_motion=reduced_motion)
    page.goto("/admin/dashboard")
    expect(page.locator(".recharts-cartesian-axis-tick-value").first).to_be_visible()
    page.get_by_role("button", name=THEME_BUTTON).click()
    return page


def test_switch_repaints_everything_in_one_frame(as_role) -> None:
    page = _open_dashboard_light(as_role)
    sample = page.evaluate(_SWITCH_AND_SAMPLE)
    assert sample is not None, "the top bar never turned dark"
    assert sample["menuGoneAtClick"] is True
    # The chart's muted tick colour is already the dark-theme value.
    assert sample["tickFill"] == "#64748b", sample
    # Colour transitions are suspended while the new tokens land.
    assert sample["switching"] is True, sample
    assert sample["pressTransition"] == "0s", sample

    # Afterwards the guard is gone and hover transitions work again.
    expect(_html(page)).not_to_have_attribute("data-theme-switching", "")
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.hasAttribute('data-theme-switching')") is False
    duration = page.evaluate(
        "getComputedStyle(document.querySelector('[class*=\"transition-colors\"]')).transitionDuration"
    )
    assert duration != "0s", duration


def test_cross_fade_only_without_reduced_motion(as_role) -> None:
    spy = """(() => { window.__vt = 0; const original = document.startViewTransition?.bind(document);
      if (original) document.startViewTransition = (cb) => { window.__vt += 1; return original(cb) } })()"""

    page = _open_dashboard_light(as_role)
    page.evaluate(spy)
    page.get_by_role("menuitemradio", name="Dark").click()
    expect(_html(page)).to_have_attribute("data-theme", "dark")
    supports = page.evaluate("typeof document.startViewTransition === 'function'")
    assert page.evaluate("window.__vt") == (1 if supports else 0)

    reduced = _open_dashboard_light(as_role, reduced_motion="reduce")
    reduced.evaluate(spy)
    reduced.get_by_role("menuitemradio", name="Dark").click()
    expect(_html(reduced)).to_have_attribute("data-theme", "dark")
    assert reduced.evaluate("window.__vt") == 0
