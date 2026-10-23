"""Staff invitation lifecycle in the portal: a host registers a visitor for
QA_MULTI (Reception, then Host), Reception approves and delegates the host
step, the delegated approver approves, the visitor checks in at the gate
(kiosk/gate-app endpoint — the portal has no check-in screen), and
Reception checks them out."""

import datetime
import re

from playwright.sync_api import Page, expect

from conftest import Api, run_tag, wait_for


def open_card(page: Page, name: str):
    """Finds the board card for `name`, searching so it's on screen however
    many other invitations exist."""
    page.goto("/staff/invitations")
    page.get_by_placeholder("Search visitor, tracking ID...").fill(name)
    # The card is an article named after the visitor; its title button is
    # the control that opens Visitor Info (accessibility "Interactive
    # Elements Are Not Nested").
    card = page.get_by_role("article", name=re.compile(rf"^{re.escape(name)},"))
    expect(card).to_be_visible()
    return card


def register_visitor(page: Page, name: str, email: str) -> None:
    page.goto("/staff/visitors/new")
    page.get_by_label("Full Name").fill(name)
    page.get_by_label("Email Address").fill(email)
    page.get_by_label("Visitor Category").select_option(label="QA Multi Step")
    page.get_by_role("button", name="Next: Visit Details →").click()

    page.get_by_label("Purpose of Visit").select_option(index=1)
    page.get_by_label("Preferred Visit Date").fill(str(datetime.date.today()))
    page.get_by_label("Preferred Visit Time").fill("10:00")
    page.get_by_label("Location").select_option(label="Main Branch")
    page.get_by_label("Building").select_option(index=1)
    page.get_by_role("button", name="Next: Carried Items →").click()
    page.get_by_role("button", name="Next: Vehicle Info →").click()
    page.get_by_role("button", name="Next: Consent Agreement →").click()
    for consent in ("Terms & Conditions", "Data Processing Consent", "Safety Guidelines"):
        page.get_by_role("checkbox", name=consent).check()
    page.get_by_role("button", name="Next: Review & Confirm →").click()
    expect(page.get_by_text(name)).to_be_visible()
    page.get_by_role("button", name="Submit Request").click()


def test_staff_invitation_lifecycle(as_role, api: Api) -> None:
    name = f"QA E2E Lifecycle {run_tag()}"
    email = f"qa.e2e.{name.split()[-1].lower()}@example.com"

    host = as_role("host")
    register_visitor(host, name, email)
    expect(host.get_by_text(re.compile(r"INV-[0-9A-F]{8}")).first).to_be_visible()

    reception = as_role("reception")
    card = open_card(reception, name)
    expect(card).to_contain_text("Level 1/2")
    card.get_by_role("button", name="Approve & Delegate").click()
    dialog = reception.get_by_role("dialog", name="Approve & Delegate")
    dialog.get_by_label("Assign next step to").select_option(label="QA Approver")
    dialog.get_by_role("button", name="Review").click()
    expect(dialog.get_by_text("QA Approver")).to_be_visible()
    dialog.get_by_role("button", name="Approve & delegate").click()
    expect(dialog).to_be_hidden()
    expect(open_card(reception, name)).to_contain_text("Level 2/2")

    approver = as_role("approver")
    card = open_card(approver, name)
    card.get_by_role("button", name="Approve", exact=True).click()
    approver_dialog = approver.get_by_role("dialog")
    approver_dialog.get_by_role("button", name="Approve Request").click()
    # The dialog closes once the approval is saved; read the status after that.
    expect(approver_dialog).to_be_hidden()

    invitation = next(
        row
        for row in api.call("GET", "/api/v1/invitations", "reception", params={"search": name})
        if row["primaryContactFullName"] == name
    )
    assert api.invitation(invitation["id"])["status"] == "approved"
    api.check_in(invitation["trackingId"])

    card = open_card(reception, name)
    card.get_by_role("button", name="Check Out", exact=True).click()
    dialog = reception.get_by_role("dialog", name="Check Out Visitor")
    dialog.get_by_role("button", name="Check Out", exact=True).click()
    expect(dialog).to_be_hidden()
    wait_for(lambda: api.invitation(invitation["id"])["status"], "checked_out")
