import json, urllib.request
from playwright.sync_api import sync_playwright
BASE = "http://localhost:5173"
req = urllib.request.Request(f"{BASE}/api/v1/auth/login", data=json.dumps({"email": "admin@example.com", "password": "admin12345"}).encode(), headers={"Content-Type": "application/json"})
token = json.load(urllib.request.urlopen(req))["data"]["accessToken"]
PUBLIC = ["/", "/visitor/request", "/visitor/track", "/admin/login", "/staff/login"]
AUTHED = ["/admin/dashboard", "/admin/branches", "/admin/branches/new", "/admin/buildings/new", "/admin/host-employees", "/admin/visitor-categories", "/admin/workflows", "/admin/invitations", "/admin/form-builder", "/admin/audit-trail", "/staff/dashboard", "/staff/visitors/new", "/reception/dashboard"]
WIDTHS = {"phone": (375, 812), "tablet": (768, 1024), "desktop": (1440, 900)}
with sync_playwright() as p:
    browser = p.chromium.launch()
    for label, (w, h) in WIDTHS.items():
        for path in PUBLIC + AUTHED:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            if path in AUTHED:
                ctx.add_init_script(f"sessionStorage.setItem('token', {json.dumps(token)})")
            page = ctx.new_page()
            try:
                page.goto(BASE + path, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(600)
                overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                name = (path.strip('/').replace('/', '_') or 'home') + f"__{label}.png"
                page.screenshot(path=f"/out/{name}", full_page=True)
                print(f"{label:8} {path:28} final={page.url.replace(BASE,''):28} hscroll={overflow}")
            except Exception as e:
                print(label, path, "ERROR", e)
            ctx.close()
    browser.close()
