"""Visitor self-service, unauthenticated: request a visit (verifying the
email with the real OTP, read from the local Mailpit) and track it."""

import datetime
import re

from playwright.sync_api import expect

from conftest import Api, JPEG, choose_option, run_tag


def test_visitor_requests_a_visit_and_tracks_it(as_role, api: Api) -> None:
    tag = run_tag()
    name, email = f"QA E2E Visitor {tag}", f"qa.e2e.visitor.{tag.lower()}@example.com"
    page = as_role("anonymous")

    page.goto("/visitor/request", wait_until="networkidle")
    page.get_by_label("Visitor's mobile number / email ID").fill(email)
    page.get_by_role("button", name="Request OTP").click()
    expect(page.get_by_label("Verification code")).to_be_visible()
    page.get_by_label("Verification code").fill(api.latest_otp(email))
    page.get_by_role("button", name="Verify and continue").click()
    expect(page.get_by_text("Contact verified.")).to_be_visible()

    page.get_by_label("Full Name").fill(name)
    expect(page.get_by_label("Email Address")).to_have_value(email)
    choose_option(page.get_by_label("Visitor Category"), "QA Single Step")
    page.locator("input[type=file]").first.set_input_files(
        {"name": "id.jpg", "mimeType": "image/jpeg", "buffer": JPEG}
    )
    page.get_by_role("button", name="Next", exact=True).click()

    choose_option(page.get_by_label("Purpose of Visit"), index=0)
    page.get_by_label("Preferred Visit Date").fill(str(datetime.date.today()))
    page.get_by_label("Preferred Visit Time").fill("11:00")
    choose_option(page.get_by_label("Location"), "Main Branch")
    choose_option(page.get_by_label("Building"), index=0)
    for _ in range(3):  # Visit Details -> Carried Items -> Vehicle Info -> Consent
        page.get_by_role("button", name="Next", exact=True).click()
    for consent in ("Terms & Conditions", "Data Processing Consent", "Safety Guidelines"):
        page.get_by_role("checkbox", name=consent).check()
    page.get_by_role("button", name="Next", exact=True).click()
    expect(page.get_by_text(name)).to_be_visible()
    page.get_by_role("button", name=re.compile(r"^Submit")).click()

    tracking = page.get_by_text(re.compile(r"INV-[0-9A-F]{8}")).first
    expect(tracking).to_be_visible()
    tracking_id = re.search(r"INV-[0-9A-F]{8}", tracking.inner_text()).group(0)

    page.goto("/visitor/track", wait_until="networkidle")
    page.get_by_placeholder("e.g. VIS-2026-00847").fill(tracking_id)
    page.get_by_role("button", name="Track Request").click()
    expect(page.get_by_text(f"ID: {tracking_id}")).to_be_visible()
    expect(page.get_by_text("Request Timeline Status")).to_be_visible()
