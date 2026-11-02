"""Sign-in, the role dashboards, and route guarding."""

import re

import pytest
from playwright.sync_api import expect

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_admin_signs_in_with_password_and_signs_out(as_role) -> None:
    # Uses one of the API's 3-per-minute login attempts for this IP.
    page = as_role("anonymous")
    page.goto("/admin/login")
    page.get_by_label("Email").fill(ADMIN_EMAIL)
    page.get_by_role("textbox", name="Password").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name="Sign In", exact=True).click()
    expect(page).to_have_url(re.compile(r"/admin/dashboard$"))
    expect(page.get_by_text("Admin User").first).to_be_visible()

    page.get_by_role("button", name="Sign out").click()
    expect(page).to_have_url(re.compile(r"/admin/login$"))
    page.goto("/admin/dashboard")
    # The guard keeps the deep link to return to after signing in again.
    expect(page).to_have_url(re.compile(r"/login\?from=%2Fadmin%2Fdashboard$"))


def test_staff_sign_in_offers_sso_only(as_role) -> None:
    page = as_role("anonymous")
    page.goto("/staff/login")
    expect(page.get_by_role("button", name="Sign in with SSO")).to_be_visible()
    expect(page.get_by_label("Password")).to_have_count(0)


@pytest.mark.parametrize(
    ("path", "button"),
    [
        ("/admin/login", "Sign In"),
        ("/admin/login", "Sign in with SSO"),
        ("/staff/login", "Sign in with SSO"),
    ],
)
def test_login_buttons_show_pointer_cursor(as_role, path: str, button: str) -> None:
    # Hover only, no submit - doesn't spend a login attempt.
    page = as_role("anonymous")
    page.goto(path)
    expect(page.get_by_role("button", name=button, exact=True)).to_have_css("cursor", "pointer")


@pytest.mark.parametrize(
    ("role", "path", "heading"),
    [
        ("admin", "/admin/dashboard", re.compile(r"Good (Morning|Afternoon|Evening)")),
        ("reception", "/reception/dashboard", re.compile(r"Good (Morning|Afternoon|Evening), QA")),
        ("host", "/staff/dashboard", re.compile(r"Good (Morning|Afternoon|Evening), QA")),
        ("security", "/staff/dashboard", re.compile(r"Good (Morning|Afternoon|Evening), QA")),
        ("reception", "/staff/invitations", "Invitations"),
    ],
)
def test_role_landing_pages_render(as_role, role: str, path: str, heading) -> None:
    page = as_role(role)
    page.goto(path)
    expect(page.get_by_role("heading", level=1, name=heading)).to_be_visible()
    expect(page.get_by_text("Something went wrong")).to_have_count(0)


def test_reception_dashboard_is_guarded_from_other_roles(as_role) -> None:
    page = as_role("security")
    page.goto("/reception/dashboard")
    expect(page).to_have_url(re.compile(r"/staff/dashboard$"))


@pytest.mark.parametrize("role", ["norole", "reception"])
def test_admin_area_is_guarded_from_non_admins(as_role, role: str) -> None:
    """QA F7, fixed by audit-and-harden §3: pages and menu entries are gated
    by the caller's permission codes, so neither a user without any nor
    standard Reception (view-only on org setup, `auth/rbac_catalog.py`) is
    offered the organisation configuration pages."""
    page = as_role(role)
    page.goto("/admin/dashboard")
    page.wait_for_load_state("networkidle")
    admin_nav = page.get_by_role("navigation").get_by_role("button", name="Organisation Configs")
    expect(admin_nav).to_have_count(0)
