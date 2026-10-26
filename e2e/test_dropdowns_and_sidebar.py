"""Dropdowns and sidebar chrome (openspec change
modernise-dropdowns-and-sidebar-chrome): the whole dropdown trigger opens
the list, the keyboard drives it, a list inside a modal isn't clipped, and
the sidebar toggle swaps between its collapse and expand states."""

import re

from playwright.sync_api import Page, expect


def open_branch_filters(page: Page):
    page.goto("/admin/branches", wait_until="networkidle")
    page.get_by_role("button", name="Filters").click()
    status = page.get_by_label("Status")
    expect(status).to_be_visible()
    return status


def listbox_for(combobox):
    return combobox.page.locator(f'[id="{combobox.get_attribute("aria-controls")}"]')


def test_clicking_a_filter_chevron_opens_the_list(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/invitations", wait_until="networkidle")
    # The board's Status filter is the multi-select (improve-board-filters-
    # multiselect), whose open list shares the "Status" label, so name the
    # trigger by role.
    status = page.get_by_role("button", name="Status", exact=True)
    # The chevron is the trigger's last icon; it used to be a dead zone.
    status.locator("svg").last.click()
    expect(status).to_have_attribute("aria-expanded", "true")
    expect(listbox_for(status).get_by_role("option").first).to_be_visible()
    page.keyboard.press("Escape")
    expect(status).to_have_attribute("aria-expanded", "false")


def test_keyboard_selects_and_escape_cancels(as_role) -> None:
    page = as_role("admin")
    status = open_branch_filters(page)
    before = status.inner_text()

    status.focus()
    page.keyboard.press("ArrowDown")
    expect(status).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Escape")
    expect(status).to_have_attribute("aria-expanded", "false")
    expect(status).to_have_text(before)
    expect(status).to_be_focused()

    page.keyboard.press("ArrowDown")
    page.keyboard.press("End")
    last = listbox_for(status).get_by_role("option").last.inner_text()
    page.keyboard.press("Enter")
    expect(status).to_have_attribute("aria-expanded", "false")
    expect(status).to_have_text(last)
    expect(status).to_be_focused()


def test_dropdown_in_a_modal_is_not_clipped(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/invitations", wait_until="networkidle")
    page.get_by_role("button", name=re.compile("Export")).first.click()
    dialog = page.get_by_role("dialog")
    status = dialog.get_by_label("Status")
    status.click()
    listbox = listbox_for(status)
    expect(listbox).to_be_visible()
    # Portalled out of the dialog, so its overflow can't cut the list off.
    expect(dialog.get_by_role("listbox")).to_have_count(0)
    box = listbox.bounding_box()
    assert box and box["y"] + box["height"] <= page.viewport_size["height"]
    listbox.get_by_role("option").last.click()
    expect(status).to_have_attribute("aria-expanded", "false")


def test_sidebar_toggle_swaps_state_and_label(as_role) -> None:
    page = as_role("admin")
    page.goto("/admin/dashboard", wait_until="networkidle")
    collapse = page.get_by_role("button", name="Collapse sidebar")
    expect(collapse).to_have_attribute("aria-expanded", "true")
    collapse.click()
    expand = page.get_by_role("button", name="Expand sidebar")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expand.hover()
    expect(page.get_by_text("Expand sidebar", exact=True)).to_be_visible()
    expand.click()
    expect(page.get_by_role("button", name="Collapse sidebar")).to_be_visible()
