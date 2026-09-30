"""Screenshots every main route at phone, tablet and desktop widths, and
fails if any page scrolls horizontally or, at phone width, if a one-column
grid gains an implicit column (fix-layout-spacing-and-footer-logo design.md
Decision 5, fix-form-grid-collapse-on-phone design.md Decision 3), so
"looks right on all devices" is checkable rather than asserted.

Needs the web dev server and the API running. Runs inside the Playwright
image (the host has no browser system libraries):

    npm run screenshots

which is:

    docker run --rm --network host -v "$PWD":/w -w /w \\
      mcr.microsoft.com/playwright/python:v1.55.0-noble \\
      bash -c "pip install -q playwright==1.55.0 && python scripts/screenshot-pages.py"

Environment:
  SCREENSHOT_BASE_URL   web origin (default http://localhost:5173)
  SCREENSHOT_EMAIL      admin login (default admin@example.com, the dev seed)
  SCREENSHOT_PASSWORD   admin password (default admin12345, the dev seed)
  SCREENSHOT_OUT        output directory (default screenshots.local, gitignored)
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
OUT = Path(os.environ.get("SCREENSHOT_OUT", "screenshots.local"))

PUBLIC = ["/", "/visitor/request", "/visitor/track", "/admin/login", "/staff/login"]
AUTHED = [
    "/admin/dashboard",
    "/admin/branches",
    "/admin/branches/new",
    "/admin/buildings/new",
    "/admin/host-employees",
    "/admin/visitor-categories",
    "/admin/workflows",
    "/admin/invitations",
    "/admin/form-builder",
    "/admin/audit-trail",
    "/staff/dashboard",
    "/staff/visitors/new",
    "/reception/dashboard",
]
WIDTHS = {"phone": (375, 812), "tablet": (768, 1024), "desktop": (1440, 900)}

# At phone width `grid-cols-1` is the active column count, so a grid showing
# more than one computed track has gained an implicit column — the
# signature of a breakpoint-less `col-span-2` inside it
# (fix-form-grid-collapse-on-phone design.md Decision 3).
IMPLICIT_COLUMNS_JS = """
() => [...document.querySelectorAll('.grid-cols-1')]
  .filter((el) => getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length > 1)
  .map((el) => `${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 4).join('.')}`)
"""


def login() -> str:
    request = urllib.request.Request(
        f"{BASE}/api/v1/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(request))["data"]["accessToken"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    token = login()
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for label, (width, height) in WIDTHS.items():
            for path in PUBLIC + AUTHED:
                context = browser.new_context(
                    viewport={"width": width, "height": height}, device_scale_factor=1
                )
                if path in AUTHED:
                    context.add_init_script(
                        f"sessionStorage.setItem('token', {json.dumps(token)})"
                    )
                page = context.new_page()
                try:
                    page.goto(BASE + path, wait_until="networkidle", timeout=20000)
                    page.wait_for_timeout(600)
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - window.innerWidth"
                    )
                    name = (path.strip("/").replace("/", "_") or "home") + f"__{label}.png"
                    page.screenshot(path=str(OUT / name), full_page=True)
                    implicit = page.evaluate(IMPLICIT_COLUMNS_JS) if label == "phone" else []
                    problems = []
                    if overflow > 0:
                        problems.append(f"HORIZONTAL SCROLL {overflow}px")
                    problems += [f"IMPLICIT GRID COLUMNS {grid}" for grid in implicit]
                    print(f"{label:8} {path:28} {'; '.join(problems) or 'ok'}")
                    failures += [f"{label} {path}: {problem}" for problem in problems]
                except Exception as error:  # noqa: BLE001 - report and keep going
                    print(f"{label:8} {path:28} ERROR {error}")
                    failures.append(f"{label} {path}: {error}")
                finally:
                    context.close()
        browser.close()
    print(f"\nScreenshots in {OUT}/")
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
