"""Rendering and MIME-structure tests for every templated email
(redesign-notification-email-templates, refine-email-templates-and-
visimio-brand). Pure rendering — no database or SMTP — so they sit in the
"unit-ish" tier (`testing-standards.md` §3); the real SMTP round trips live
in `invitations/tests.py`'s Mailpit tests.
"""

import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from vmss_api.core import email_rendering, portal_links
from vmss_api.core.config import settings
from vmss_api.core.email_rendering import (
    TEMPLATE_TONES,
    TONES,
    TemplateRenderError,
    display_name,
    render_email,
    visit_datetime,
)
from vmss_api.core.emailing import (
    BRAND_LOGO_CID,
    build_message,
    make_attachment,
    make_inline_image,
)
from vmss_api.invitations import tasks as invitation_tasks

# The value from the design mock that surfaced the greeting bug.
_OPAQUE_NAME = "ccbb9a1e304730e0512d912e18f6ce6591bee85c26e3cdb7b5d4b89a3549bb731a3a"

# (template, tone, pill, heading) — email-notifications "Each Notification
# Type Carries Accurate, Type-Specific Content".
_TYPES = [
    ("visit_confirmation", "success", "Confirmed", "Your visit is confirmed"),
    ("tracking_only", "pending", "Pending approval", "We've received your visit request"),
    ("denial", "danger", "Not approved", "Your visit request wasn't approved"),
    ("reschedule", "info", "Rescheduled", "Your visit has been rescheduled"),
    ("edit", "info", "Details updated", "Your visit details have changed"),
    ("submission_role", "pending", "Action needed", "New visit request awaiting triage"),
    ("host_assigned", "brand", "You're the host", "You've been named host for a visit"),
    ("poc_assigned", "brand", "Point of contact", "You're the point of contact for a visit"),
]
_INVITATION_TEMPLATES = [name for name, *_ in _TYPES]
_ALL_TEMPLATES = [*_INVITATION_TEMPLATES, "verification_code", "daily_snapshot"]
_PLACE = "Tower A · Technopark Campus · Phase 1, Trivandrum"


def _context(**overrides: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "company_name": "Acme Corp",
        "logo_url": None,
        "recipient_name": "Meera Krishnan",
        "recipient_email": "meera@example.com",
        "tracking_id": "INV-B8490B0B",
        "visitor_name": "Meera Krishnan",
        "purpose": "Interview",
        "visit_date": date(2026, 10, 14),
        "visit_time": time(10, 30),
        "previous_visit_date": date(2026, 10, 12),
        "previous_visit_time": time(9, 0),
        "duration": "1 hour",
        "department": "Engineering",
        "place": _PLACE,
        "front_desk_contact": "+91 80000 22233",
        "contact_title": "Your point of contact",
        "contact_name": "Priya Nair",
        "contact_detail": "+91 90000 11122",
        "is_approved": True,
        # The inline fallback; URL-image rendering is covered separately below.
        "qr_src": "cid:visit-qr@vmss",
        "denial_reason": "Visitor not on the expected list",
        "visitor_phone": "+91 98765 43210",
        "visitor_email": "meera@example.com",
        # verification_code / daily_snapshot
        "code": "763090",
        "minutes": 5,
        "report_date": date(2026, 9, 30),
        "total_branches": 1,
        "totals": SimpleNamespace(
            buildings=2,
            floors=6,
            departments=8,
            reception_desks=1,
            security_gates=3,
            active_employees=60,
        ),
        "branches": [
            SimpleNamespace(
                branch_name="Technopark Campus",
                branch_code="TPK",
                building_count=2,
                floor_count=6,
                department_count=8,
                reception_desk_count=1,
                security_gate_count=3,
                active_employee_count=60,
            )
        ],
    }
    context.update(overrides)
    return context


def _visible_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    for entity, char in (("&#39;", "'"), ("&amp;", "&"), ("&mdash;", "—"), ("&copy;", "©")):
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text)


# --- Filters -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "email", "expected"),
    [
        ("Meera Krishnan", None, "Meera Krishnan"),
        ("  Meera  ", None, "Meera"),
        (_OPAQUE_NAME, None, None),
        ("69c50553297dbc5c98c455d2a300", None, None),
        ("3f2b9c1e-8a4d-4f6b-9c2e-1a2b3c4d5e6f", None, None),
        ("host@acme.test", "HOST@acme.test", None),
        ("", None, None),
        ("   ", None, None),
        (None, None, None),
    ],
)
def test_display_name(value: str | None, email: str | None, expected: str | None) -> None:
    assert display_name(value, email) == expected


def test_visit_datetime_formats_date_and_time() -> None:
    assert visit_datetime(date(2026, 10, 14), time(10, 30)) == "Wed, 14 Oct 2026 · 10:30 AM"
    assert visit_datetime(date(2026, 10, 14), time(0, 5)) == "Wed, 14 Oct 2026 · 12:05 AM"
    assert visit_datetime(date(2026, 10, 14), time(17, 46)) == "Wed, 14 Oct 2026 · 5:46 PM"


def test_visit_datetime_date_only_and_none() -> None:
    assert visit_datetime(date(2026, 10, 14)) == "Wed, 14 Oct 2026"
    assert visit_datetime(None, time(10, 30)) is None


# --- Tones -------------------------------------------------------------------


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(fg: str, bg: str) -> float:
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("tone", sorted(TONES))
def test_tone_text_meets_wcag_aa(tone: str) -> None:
    palette = TONES[tone]
    assert _contrast(palette.pill_fg, palette.pill_bg) >= 4.5
    assert _contrast(palette.heading_fg, palette.tint_bg) >= 4.5


@pytest.mark.parametrize(("template_name", "tone", "pill", "heading"), _TYPES)
def test_each_type_renders_its_tone_pill_and_heading_as_subject(
    template_name: str, tone: str, pill: str, heading: str
) -> None:
    rendered = render_email(template_name, _context())
    html_text = _visible_text(rendered.html)
    assert TEMPLATE_TONES[template_name] == tone
    assert rendered.subject == heading
    assert heading in html_text
    assert pill in html_text
    assert f"background-color:{TONES[tone].pill_bg}" in rendered.html
    assert heading in rendered.text
    assert f"[{pill.upper()}]" in rendered.text


# --- Branding ----------------------------------------------------------------


@pytest.mark.parametrize("template_name", _ALL_TEMPLATES)
def test_every_email_carries_visimio_branding(template_name: str) -> None:
    rendered = render_email(template_name, _context())
    year = datetime.now(UTC).year
    for part in (rendered.html, rendered.text):
        assert "VisitorPass" not in part
    # No asset base URL in tests (conftest), so the header is the text
    # wordmark — never an inline logo part.
    assert 'Visi<span style="color:#22d3ee;">mio</span>' in rendered.html
    assert f"cid:{BRAND_LOGO_CID}" not in rendered.html
    assert f"© {year} Visimio. All rights reserved." in _visible_text(rendered.html)
    assert "Powered by Visimio" in _visible_text(rendered.html)
    assert f"(c) {year} Visimio" in rendered.text


def test_no_template_file_mentions_the_old_brand() -> None:
    templates = Path(__file__).parents[1] / "src/vmss_api/core/email_templates"
    for path in templates.iterdir():
        assert "VisitorPass" not in path.read_text(), path.name


def test_tenant_logo_replaces_the_visimio_logo() -> None:
    html = render_email("tracking_only", _context(logo_url="https://cdn.example.com/acme.png")).html
    assert '<img src="https://cdn.example.com/acme.png" alt="Acme Corp"' in html
    assert f"cid:{BRAND_LOGO_CID}" not in html
    assert "Powered by" in html


# --- Per-type content --------------------------------------------------------


def test_confirmation_shows_when_where_and_who() -> None:
    rendered = render_email("visit_confirmation", _context())
    text = _visible_text(rendered.html)
    for expected in (
        "Wed, 14 Oct 2026 · 10:30 AM",
        _PLACE,
        "Engineering",
        "Your point of contact",
        "Priya Nair",
        "+91 90000 11122",
        "Before you arrive",
        "Need to change your plans?",
        "+91 80000 22233",
    ):
        assert expected in text, expected
        assert expected in rendered.text or expected.upper() in rendered.text, expected


def test_denial_uses_red_reason_callout_and_checklist() -> None:
    rendered = render_email("denial", _context())
    text = _visible_text(rendered.html)
    danger = TONES["danger"]
    assert f"border-left:4px solid {danger.accent}" in rendered.html
    assert "Reason given" in text and "Visitor not on the expected list" in text
    assert "What you can do" in text
    assert "Get in touch with the front desk on +91 80000 22233" in text
    assert "Please quote your tracking ID INV-B8490B0B in any follow-up." in text


def test_denial_without_reason_omits_the_callout() -> None:
    assert "Reason given" not in render_email("denial", _context(denial_reason=None)).html


def test_received_email_shows_the_approval_timeline() -> None:
    rendered = render_email("tracking_only", _context())
    text = _visible_text(rendered.html)
    assert "What happens next" in text
    assert text.index("Request submitted") < text.index("Under review") < text.index("Confirmation")
    assert "Request submitted (done)" in rendered.text
    assert "Under review (in progress)" in rendered.text
    assert "cid:visit-qr@vmss" not in rendered.html


def test_verification_code_email() -> None:
    rendered = render_email("verification_code", _context())
    text = _visible_text(rendered.html)
    assert rendered.subject == "Your verification code"
    assert "763090" in text and "Verification code" in text
    assert "The code expires in 5 minutes and can only be used once." in text
    assert "Keep it private" in text
    assert "Hi Meera" not in text and "Hello," not in text
    assert "Verification code: 763090" in rendered.text
    assert "INV-B8490B0B" not in rendered.html + rendered.text


def test_daily_snapshot_email_lists_branch_figures() -> None:
    rendered = render_email("daily_snapshot", _context())
    text = _visible_text(rendered.html)
    assert rendered.subject == "Daily branch rollup — Wed, 30 Sep 2026"
    assert "Technopark Campus" in text and "TPK" in text
    assert "Technopark Campus (TPK): 2 building(s)" in rendered.text


def test_daily_snapshot_with_no_branches() -> None:
    rendered = render_email("daily_snapshot", _context(branches=[], total_branches=0))
    assert "There are no branches to report yet." in _visible_text(rendered.html)
    assert "There are no branches to report yet." in rendered.text


@pytest.mark.parametrize("template_name", _INVITATION_TEMPLATES)
def test_absent_values_omit_their_rows(template_name: str) -> None:
    rendered = render_email(
        template_name,
        _context(
            duration=None,
            department=None,
            place=None,
            purpose=None,
            previous_visit_date=None,
            visitor_phone=None,
            contact_name=None,
        ),
    )
    for part in (_visible_text(rendered.html), rendered.text):
        assert "None" not in part
        for label in ("Expected duration", "Department", "Place of visit", "Purpose", "Previously"):
            assert label not in part


@pytest.mark.parametrize("template_name", _INVITATION_TEMPLATES)
def test_opaque_identifier_name_is_never_shown(template_name: str) -> None:
    rendered = render_email(
        template_name, _context(recipient_name=_OPAQUE_NAME, visitor_name=_OPAQUE_NAME)
    )
    assert _OPAQUE_NAME not in rendered.html
    assert _OPAQUE_NAME not in rendered.text
    assert "Hello," in rendered.text


def test_real_name_is_greeted() -> None:
    rendered = render_email("visit_confirmation", _context())
    assert "Hi Meera Krishnan," in rendered.html
    assert "Hi Meera Krishnan," in rendered.text


@pytest.mark.parametrize("template_name", _INVITATION_TEMPLATES)
def test_dates_are_human_readable(template_name: str) -> None:
    rendered = render_email(template_name, _context())
    for part in (rendered.html, rendered.text):
        assert "Wed, 14 Oct 2026" in part
        assert "2026-10-14" not in part
        assert "10:30:00" not in part


def test_host_assigned_matches_the_mock_copy() -> None:
    rendered = render_email("host_assigned", _context(recipient_name=_OPAQUE_NAME))
    text = _visible_text(rendered.html)
    assert "You're now the host for Meera Krishnan's visit." in text
    assert "You'll be notified when they check in." in text
    assert "search for tracking ID INV-B8490B0B" in text
    assert _PLACE in text


def test_reschedule_plain_text_carries_the_same_information() -> None:
    rendered = render_email("reschedule", _context())
    assert "INV-B8490B0B" in rendered.text
    assert "New date & time: Wed, 14 Oct 2026 · 10:30 AM" in rendered.text
    assert "Previously: Mon, 12 Oct 2026 · 9:00 AM" in rendered.text
    assert "YOUR CHECK-IN QR CODE" in rendered.text


# --- QR block ----------------------------------------------------------------


@pytest.mark.parametrize("template_name", _INVITATION_TEMPLATES)
def test_only_confirmation_and_reschedule_embed_the_qr_pass(template_name: str) -> None:
    rendered = render_email(template_name, _context())
    has_qr = "cid:visit-qr@vmss" in rendered.html
    assert has_qr is (template_name in {"visit_confirmation", "reschedule"})
    assert ("Your check-in pass" in rendered.html) is has_qr


def test_reschedule_without_qr_says_the_pass_follows_approval() -> None:
    rendered = render_email("reschedule", _context(qr_src=None, is_approved=False))
    assert "cid:visit-qr@vmss" not in rendered.html
    assert "as soon as it's approved" in rendered.text


def test_visit_confirmation_qr_block_shows_tracking_id() -> None:
    html = render_email("visit_confirmation", _context()).html
    block = html[html.index("Your check-in pass") : html.index("Before you arrive")]
    assert 'src="cid:visit-qr@vmss"' in block
    assert "INV-B8490B0B" in block
    assert "reception or the security gate" in block


def test_qr_text_part_no_longer_mentions_an_attachment() -> None:
    text = render_email("visit_confirmation", _context()).text
    assert "attached" not in text
    assert "images enabled" in text


@pytest.mark.parametrize(
    ("is_approved", "expected"), [(True, "is still valid"), (False, "as soon as it's approved")]
)
def test_edit_pass_sentence_follows_approval_state(is_approved: bool, expected: str) -> None:
    rendered = render_email("edit", _context(is_approved=is_approved))
    assert expected in rendered.text
    assert "cid:visit-qr@vmss" not in rendered.html


def test_non_date_value_raises_template_render_error() -> None:
    """A plain Python error inside a filter still surfaces as
    `TemplateRenderError`, so callers take the plain-text fallback path
    instead of retrying forever.
    """
    with pytest.raises(TemplateRenderError):
        render_email("reschedule", _context(visit_date="2026-10-14"))


# --- MIME structure (email-notifications "The Sender Interface Supports
# Inline Images") ------------------------------------------------------------


def test_inline_images_and_logo_are_related_parts_of_the_html_body() -> None:
    message = build_message(
        to="visitor@example.com",
        subject="s",
        body="text",
        html_body=f'<img src="cid:{BRAND_LOGO_CID}"><img src="cid:visit-qr@vmss">',
        inline_images=[make_inline_image(b"\x89PNG-inline", "image/png", "visit-qr@vmss")],
    )
    structure = [part.get_content_type() for part in message.walk()]
    assert structure == [
        "multipart/alternative",
        "text/plain",
        "multipart/related",
        "text/html",
        "image/png",
        "image/png",
    ]
    cids = [part["Content-ID"] for part in message.walk() if part.get("Content-ID")]
    assert cids == ["<visit-qr@vmss>", f"<{BRAND_LOGO_CID}>"]
    assert all(
        part.get_content_disposition() == "inline"
        for part in message.walk()
        if part.get("Content-ID")
    )


def test_from_header_carries_the_visimio_display_name() -> None:
    message = build_message(to="a@example.com", subject="s", body="text")
    assert message["From"].startswith("Visimio <")


def test_logo_is_not_attached_when_the_html_does_not_reference_it() -> None:
    message = build_message(to="a@example.com", subject="s", body="text", html_body="<p>x</p>")
    assert [part.get_content_type() for part in message.walk()] == [
        "multipart/alternative",
        "text/plain",
        "text/html",
    ]


def test_regular_attachment_is_still_supported() -> None:
    message = build_message(
        to="a@example.com",
        subject="s",
        body="text",
        attachment=make_attachment(b"x", "report.csv", "text/csv"),
    )
    assert [part.get_filename() for part in message.walk() if part.get_filename()] == ["report.csv"]


# --- Images by URL (serve-email-images-by-url-and-complete-contact) --------

_ASSET_BASE = "https://api.example.test"
_SIGNED_QR = f"{_ASSET_BASE}/api/v1/public/email-assets/t/qr/i.png?exp=1&sig=abc"


@pytest.fixture
def _asset_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_asset_base_url", _ASSET_BASE)


@pytest.mark.parametrize("template_name", _ALL_TEMPLATES)
def test_configured_base_url_references_every_image_by_absolute_url(
    _asset_base_url, template_name: str
) -> None:
    html = render_email(template_name, _context(qr_src=_SIGNED_QR)).html
    assert (
        f'<img src="{_ASSET_BASE}/api/v1/public/email-assets/visimio-logo.png" alt="Visimio"'
        in html
    )
    assert "cid:" not in html
    srcs = re.findall(r'<img src="([^"]+)"', html)
    assert srcs and all(src.startswith(f"{_ASSET_BASE}/") for src in srcs)


def test_configured_confirmation_qr_block_uses_the_signed_url(_asset_base_url) -> None:
    html = render_email("visit_confirmation", _context(qr_src=_SIGNED_QR)).html
    block = html[html.index("Your check-in pass") : html.index("Before you arrive")]
    assert f'src="{_SIGNED_QR.replace("&", "&amp;")}"' in block
    assert "INV-B8490B0B" in block


def test_unconfigured_base_url_warns_once_and_uses_the_wordmark(monkeypatch) -> None:
    monkeypatch.setattr(email_rendering, "_warned_base_url_unset", False)
    with capture_logs() as captured:
        first = render_email("visit_confirmation", _context())
        render_email("tracking_only", _context())
    warnings = [e for e in captured if e["event"] == "email_asset_base_url_unset"]
    assert len(warnings) == 1
    assert warnings[0]["log_level"] == "warning"
    assert warnings[0]["setting"] == "EMAIL_ASSET_BASE_URL"
    assert "Visi<span" in first.html
    assert 'src="cid:visit-qr@vmss"' in first.html


def test_configured_confirmation_message_is_only_text_and_html(_asset_base_url) -> None:
    rendered = render_email("visit_confirmation", _context(qr_src=_SIGNED_QR))
    message = build_message(
        to="visitor@example.com",
        subject=rendered.subject,
        body=rendered.text,
        html_body=rendered.html,
    )
    structure = [part.get_content_type() for part in message.walk()]
    assert structure == ["multipart/alternative", "text/plain", "text/html"]
    assert not any(part.get("Content-ID") for part in message.walk())
    assert not any(part.get_content_disposition() for part in message.walk())


# --- Portal links (add-portal-links-to-emails) --------------------------------

_PORTAL = "https://visit.example.test"
_TRACK_URL = f"{_PORTAL}/visitor/track"
_STAFF_URL = f"{_PORTAL}/staff/login"

# (template, button label, URL) — email-notifications "Actionable Emails
# Link to the Relevant Portal Page".
_CTA_TYPES = [
    ("tracking_only", "Track your request", _TRACK_URL),
    ("visit_confirmation", "View your visit", _TRACK_URL),
    ("reschedule", "View your visit", _TRACK_URL),
    ("edit", "View your visit", _TRACK_URL),
    ("denial", "Submit a new request", f"{_PORTAL}/visitor/request"),
    ("submission_role", "Review request", _STAFF_URL),
    ("host_assigned", "View visit", _STAFF_URL),
    ("poc_assigned", "View visit", _STAFF_URL),
]


@pytest.fixture
def _portal_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "staff_portal_url", _PORTAL)


@pytest.fixture
def _portal_unset(monkeypatch) -> None:
    monkeypatch.setattr(settings, "staff_portal_url", None)
    monkeypatch.setattr(portal_links, "_warned_base_url_unset", False)


def _link_context(**overrides: Any) -> dict[str, Any]:
    """`_context()` plus the URL keys `_invitation_email_context` adds."""
    return _context(
        visitor_track_url=portal_links.visitor_track_url(),
        visitor_request_url=portal_links.visitor_request_url(),
        staff_login_url=portal_links.staff_login_url(),
        **overrides,
    )


def _render_with_cta(template_name: str, context: dict[str, Any]) -> tuple[str, str, str | None]:
    return invitation_tasks._render_or_fallback(template_name, context, fallback_subject="x")


def test_portal_link_paths(_portal_base_url) -> None:
    assert portal_links.visitor_track_url() == _TRACK_URL
    assert portal_links.visitor_request_url() == f"{_PORTAL}/visitor/request"
    assert portal_links.staff_login_url() == _STAFF_URL


@pytest.mark.parametrize(
    "value", [f"{_PORTAL}/staff/login", f"{_PORTAL}/staff/login/", f"{_PORTAL}/?next=/x"]
)
def test_portal_link_keeps_only_the_origin_of_a_page_url(monkeypatch, value: str) -> None:
    """Deployments set STAFF_PORTAL_URL to the staff login page, not the
    bare origin.
    """
    monkeypatch.setattr(settings, "staff_portal_url", value)
    assert portal_links.visitor_track_url() == f"{_PORTAL}/visitor/track"
    assert portal_links.staff_login_url() == f"{_PORTAL}/staff/login"


def test_portal_link_strips_trailing_slash_and_whitespace(monkeypatch) -> None:
    monkeypatch.setattr(settings, "staff_portal_url", f"  {_PORTAL}/ ")
    assert portal_links.visitor_request_url() == f"{_PORTAL}/visitor/request"


@pytest.mark.parametrize("value", ["__STAFF_PORTAL_URL__", "visit.example.test", "  "])
def test_unreplaced_token_or_non_url_counts_as_unset(monkeypatch, value: str) -> None:
    """An environment whose pipeline didn't replace the token must send no
    link rather than `__STAFF_PORTAL_URL__/visitor/track?...`.
    """
    monkeypatch.setattr(settings, "staff_portal_url", value)
    monkeypatch.setattr(portal_links, "_warned_base_url_unset", False)
    assert portal_links.visitor_track_url() is None
    assert portal_links.staff_login_url() is None


def test_unset_portal_url_returns_none_and_warns_once(_portal_unset) -> None:
    with capture_logs() as captured:
        assert portal_links.visitor_track_url() is None
        assert portal_links.visitor_request_url() is None
        assert portal_links.staff_login_url() is None
    warnings = [e for e in captured if e["event"] == "portal_base_url_unset"]
    assert len(warnings) == 1
    assert warnings[0]["log_level"] == "warning"
    assert warnings[0]["setting"] == "STAFF_PORTAL_URL"


@pytest.mark.parametrize(("template_name", "label", "url"), _CTA_TYPES)
def test_each_actionable_email_links_to_its_portal_page(
    _portal_base_url, template_name: str, label: str, url: str
) -> None:
    _, text, html = _render_with_cta(template_name, _link_context())
    assert html is not None
    assert f'href="{url}"' in html
    assert label in _visible_text(html)
    assert f"{label}: {url}" in text
    # The manual route stays for a reader who can't follow the link.
    assert "INV-B8490B0B" in _visible_text(html)


def test_submission_email_no_longer_links_to_the_portal_root(_portal_base_url) -> None:
    _, text, html = _render_with_cta("submission_role", _link_context())
    assert html is not None
    assert f'href="{_PORTAL}"' not in html and f'href="{_PORTAL}/"' not in html
    assert "Open staff portal" not in html + text


@pytest.mark.parametrize(("template_name", "label", "url"), _CTA_TYPES)
def test_unset_portal_url_omits_the_link_but_still_renders(
    _portal_unset, template_name: str, label: str, url: str
) -> None:
    subject, text, html = _render_with_cta(template_name, _link_context())
    assert html is not None and subject != "x"
    assert "<a href" not in html
    assert f"{label}:" not in text
    assert "https://" not in text


def test_verification_code_email_carries_no_links(_portal_base_url) -> None:
    # Even a stray `cta` in the context must not surface in the code email.
    context = _link_context(cta={"label": "x", "url": _TRACK_URL})
    rendered = render_email("verification_code", context)
    assert "<a href" not in rendered.html
    assert "http://" not in rendered.text and "https://" not in rendered.text


@pytest.mark.parametrize(("template_name", "label", "url"), _CTA_TYPES)
def test_links_carry_no_personal_data(
    _portal_base_url, template_name: str, label: str, url: str
) -> None:
    _, _, html = _render_with_cta(template_name, _link_context())
    assert html is not None
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs
    for href in hrefs:
        for value in ("Meera", "meera@example.com", "98765", "+91"):
            assert value not in href


def test_fallback_email_keeps_the_link(_portal_base_url) -> None:
    subject, body, html = invitation_tasks._render_or_fallback(
        "tracking_only",
        _link_context(visit_date="not-a-date"),
        fallback_subject="We've received your visit request",
    )
    assert html is None
    assert subject == "We've received your visit request"
    assert "INV-B8490B0B" in body
    assert f"Track your request: {_TRACK_URL}" in body


def test_fallback_email_without_portal_url_has_no_link(_portal_unset) -> None:
    _, body, html = invitation_tasks._render_or_fallback(
        "tracking_only", _link_context(visit_date="not-a-date"), fallback_subject="x"
    )
    assert html is None
    assert "https://" not in body
