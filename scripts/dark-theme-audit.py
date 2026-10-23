"""Renders the staff and admin routes in the dark theme and reports what
doesn't follow it (fix-dark-theme-rendering design.md D6):

- text below WCAG AA against the background behind it (reported for
  review: an element over an absolutely positioned sibling, like a toggle's
  sliding pill, is a known false positive);
- a <select> with a transparent background, whose native option list
  opens on the browser's white canvas with the theme's light text. This one
  fails the run.

With --switch it also loads each route in light, switches to Dark through
the top-bar control, and fails if any element's colours differ from a
fresh dark load (theme-mode "Switching theme repaints in one clean step").

Needs the web dev server and the API running. Runs inside the Playwright
image, like screenshot-pages.py:

    npm run audit:dark            # or: npm run audit:dark -- --switch

Environment: SCREENSHOT_BASE_URL, SCREENSHOT_EMAIL, SCREENSHOT_PASSWORD and
SCREENSHOT_OUT, as for screenshot-pages.py; screenshots go to <OUT>/dark.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SCREENSHOT_BASE_URL", "http://localhost:5173").rstrip("/")
EMAIL = os.environ.get("SCREENSHOT_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("SCREENSHOT_PASSWORD", "admin12345")
OUT = Path(os.environ.get("SCREENSHOT_OUT", "screenshots.local")) / "dark"
THEME_KEY = "vmss.themeMode"  # theme-mode-context THEME_MODE_STORAGE_KEY

ROUTES = [
    "/admin/dashboard",
    "/admin/branches",
    "/admin/branches/new",
    "/admin/buildings",
    "/admin/floors",
    "/admin/departments",
    "/admin/host-employees",
    "/admin/visitor-categories",
    "/admin/workflows",
    "/admin/invitations",
    "/admin/form-builder",
    "/admin/audit-trail",
    "/admin/roles",
    "/admin/kiosks",
    "/admin/security-gates",
    "/admin/reception-desks",
    "/admin/organisation-configs",
    "/staff/dashboard",
    "/staff/invitations",
    "/staff/visitors/new",
    "/staff/calendar",
    "/reception/dashboard",
]

SCAN_JS = r"""
() => {
  const parse = (c) => { const m = c.match(/[\d.]+/g); return m ? m.map(Number) : null }
  const channel = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
  const lum = ([r, g, b]) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
  const opaque = (c) => c && (c.length < 4 || c[3] > 0.5)
  const bgOf = (el) => {
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (opaque(c)) return c }
    return [255, 255, 255]
  }
  const out = { lowContrast: [], transparentSelects: [] }
  const seen = new Set()
  for (const el of document.querySelectorAll('body *')) {
    const s = getComputedStyle(el)
    if (s.display === 'none' || s.visibility === 'hidden' || (el.offsetParent === null && s.position !== 'fixed')) continue
    if (el.tagName === 'SELECT' && !opaque(parse(s.backgroundColor))) {
      out.transparentSelects.push(el.getAttribute('aria-label') || el.id || String(el.className).slice(0, 80))
    }
    const text = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join(' ').trim()
    const fg = parse(s.color)
    if (!text || !fg || (fg.length === 4 && fg[3] === 0)) continue
    const bg = bgOf(el)
    const [high, low] = [lum(fg), lum(bg)].sort((x, y) => y - x)
    const ratio = (high + 0.05) / (low + 0.05)
    const size = parseFloat(s.fontSize)
    const large = size >= 24 || (size >= 18.66 && Number(s.fontWeight) >= 700)
    const key = text.slice(0, 40) + s.color + bg
    if (ratio < (large ? 3 : 4.5) && !seen.has(key)) {
      seen.add(key)
      out.lowContrast.push(`${ratio.toFixed(2)}:1  "${text.slice(0, 40)}"  ${s.color} on rgb(${bg.slice(0, 3).join(',')})`)
    }
  }
  return out
}
"""

COLOURS_JS = r"""
() => [...document.querySelectorAll('body *')].map((el) => {
  const s = getComputedStyle(el)
  return [el.tagName, s.color, s.backgroundColor, s.borderTopColor, s.fill, s.stroke].join('|')
})
"""


def login() -> str:
    request = urllib.request.Request(
        f"{BASE}/api/v1/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(request))["data"]["accessToken"]


def open_page(browser, token: str, path: str, mode: str):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    # Seed the stored mode once, so a switch made on the page isn't undone by
    # a later navigation re-running the init script.
    context.add_init_script(
        f"sessionStorage.setItem('token', {json.dumps(token)});"
        "if (!sessionStorage.getItem('auditSeeded')) {"
        f"  localStorage.setItem({json.dumps(THEME_KEY)}, JSON.stringify({json.dumps(mode)}));"
        "  sessionStorage.setItem('auditSeeded', '1') }"
    )
    page = context.new_page()
    page.goto(BASE + path, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(800)
    return context, page


def main() -> int:
    check_switch = "--switch" in sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    token = login()
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for path in ROUTES:
            try:
                context, page = open_page(browser, token, path, "dark")
                name = path.strip("/").replace("/", "_")
                page.screenshot(path=str(OUT / f"{name}.png"))
                found = page.evaluate(SCAN_JS)
                fresh = page.evaluate(COLOURS_JS) if check_switch else None
                context.close()
                print(f"{path:30} transparent selects: {len(found['transparentSelects'])}  low contrast: {len(found['lowContrast'])}")
                for label in found["transparentSelects"]:
                    print(f"    SELECT  {label}")
                    failures.append(f"{path}: transparent <select> {label}")
                for line in found["lowContrast"]:
                    print(f"    LOW     {line}")
                if check_switch:
                    context, page = open_page(browser, token, path, "light")
                    page.get_by_label("Theme:").first.click()
                    page.get_by_role("menuitemradio", name="Dark").click()
                    page.wait_for_timeout(1200)
                    switched = page.evaluate(COLOURS_JS)
                    context.close()
                    diffs = sum(1 for a, b in zip(fresh, switched) if a != b) + abs(len(fresh) - len(switched))
                    print(f"    SWITCH  {diffs} element(s) differ from a fresh dark load")
                    if diffs:
                        failures.append(f"{path}: {diffs} element(s) differ after a live switch")
            except Exception as error:  # noqa: BLE001 - report and keep going
                print(f"{path:30} ERROR {error}")
                failures.append(f"{path}: {error}")
        browser.close()
    if failures:
        print("\nFAILED:\n" + "\n".join(failures))
        return 1
    print(f"\nok — screenshots in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
