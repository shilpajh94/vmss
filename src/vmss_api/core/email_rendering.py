"""Jinja2-based email rendering (role-based-invitation-workflow,
`email-notifications` capability). A rendering step in front of the
existing `EmailSender` interface (`core/emailing.py`), not a parallel
dispatch path, so a provider swap never has to touch template code.

Templates live in `core/email_templates/` as a pair per notification type:
`<name>.html` extends `base.html` (the shared Visimio layout) and
defines `subject` + `content` blocks; `<name>.txt` extends `base.txt` and
carries the same information as plain text
(redesign-notification-email-templates/design.md Decision 3). Both are
rendered from one context through the same filters, so subject, HTML and
plain text can't drift apart.
"""

import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from html import unescape as html_unescape
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError, Undefined, select_autoescape

from vmss_api.core import email_assets
from vmss_api.core.config import settings
from vmss_api.core.logging import logger

_TEMPLATES_DIR = Path(__file__).parent / "email_templates"

# Fixed English names rather than `strftime("%a")`/`%b`, so the container's
# locale can never change what a visitor sees (design.md Decision 6).
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# A single whitespace-free token of 16+ id-ish characters — a hex digest,
# UUID, base64 blob, or IdP subject — rather than a person's name. Seen in
# practice when an SSO IdP sends no `name` claim ("Hi ccbb9a1e3047…").
_OPAQUE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_\-+/=]{16,}$")


def display_name(value: str | None, email: str | None = None) -> str | None:
    """A name safe to address someone by, or `None` when the stored value
    isn't one (email-notifications "Greetings Use a Trustworthy Display
    Name or a Neutral Fallback").
    """
    # `Undefined`: the caller's context simply didn't carry this name.
    if value is None or isinstance(value, Undefined):
        return None
    if isinstance(email, Undefined):
        email = None
    name = value.strip()
    if not name:
        return None
    if email is not None and name.casefold() == email.strip().casefold():
        return None
    if _OPAQUE_IDENTIFIER.fullmatch(name):
        return None
    return name


def visit_datetime(value: date | None, at: time | None = None) -> str | None:
    """`Wed, 14 Oct 2026 · 10:30 AM`, or just the date when no time is set."""
    if value is None or isinstance(value, Undefined):
        return None
    if isinstance(at, Undefined):
        at = None
    formatted = f"{_WEEKDAYS[value.weekday()]}, {value.day} {_MONTHS[value.month - 1]} {value.year}"
    if at is not None:
        hour = at.hour % 12 or 12
        meridiem = "AM" if at.hour < 12 else "PM"
        formatted += f" · {hour}:{at.minute:02d} {meridiem}"
    return formatted


def _build_env(*, html: bool) -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]) if html else False,
        trim_blocks=not html,
        lstrip_blocks=not html,
        keep_trailing_newline=False,
    )
    env.filters["display_name"] = display_name
    env.filters["visit_datetime"] = visit_datetime
    return env


_html_env = _build_env(html=True)
_text_env = _build_env(html=False)


class TemplateRenderError(RuntimeError):
    """Raised when a named template fails to render for any reason. Callers
    (`invitations/tasks.py`) catch this and fall back to a minimal
    plain-text email — spec.md "Template Rendering Failure Falls Back to a
    Minimal Plain-Text Email" — rather than failing to send anything at all.
    """


@dataclass(frozen=True)
class Tone:
    """One status theme (refine-email-templates-and-visimio-brand design.md
    Decision 1). Inline hex values, because most mail clients strip
    `<style>` classes; templates read these via the injected `t`, never a
    literal colour of their own.
    """

    pill_bg: str
    pill_fg: str
    accent: str
    tint_bg: str
    tint_border: str
    heading_fg: str


TONES: dict[str, Tone] = {
    "success": Tone("#dcfce7", "#166534", "#16a34a", "#f0fdf4", "#86efac", "#166534"),
    "pending": Tone("#fef3c7", "#92400e", "#d97706", "#fffbeb", "#fcd34d", "#92400e"),
    "danger": Tone("#fee2e2", "#b91c1c", "#ef4444", "#fef2f2", "#fca5a5", "#b91c1c"),
    "info": Tone("#dbeafe", "#1d4ed8", "#3b82f6", "#eff6ff", "#93c5fd", "#1d4ed8"),
    "brand": Tone("#ecfeff", "#0b7a74", "#0b8b84", "#ecfeff", "#67e8f9", "#0b7a74"),
}

# Which theme each email type renders in (email-notifications "Each
# Notification Type Carries Accurate, Type-Specific Content").
TEMPLATE_TONES: dict[str, str] = {
    "visit_confirmation": "success",
    "tracking_only": "pending",
    "submission_role": "pending",
    "denial": "danger",
    "reschedule": "info",
    "edit": "info",
    "host_assigned": "brand",
    "poc_assigned": "brand",
    "verification_code": "brand",
    "daily_snapshot": "brand",
}


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


_BLANK_LINE_RUNS = re.compile(r"\n{3,}")


_warned_base_url_unset = False


def _logo_src() -> str | None:
    """The absolute header-logo URL, or `None` (text wordmark) when no
    public asset base is configured — warned once per process, not per
    email (serve-email-images-by-url-and-complete-contact design.md
    Decision 3).
    """
    global _warned_base_url_unset
    src = email_assets.logo_url()
    if src is None and not _warned_base_url_unset:
        _warned_base_url_unset = True
        logger.warning(
            "email_asset_base_url_unset",
            setting="EMAIL_ASSET_BASE_URL",
            effect="text wordmark header; check-in QR embedded inline",
        )
    return src


def render_email(template_name: str, context: dict[str, Any]) -> RenderedEmail:
    """Renders `<template_name>.html` and `<template_name>.txt`. The
    subject is the template's `heading` block — email-notifications "The
    email's subject line SHALL match its heading" — and is handed to the
    text template as `heading` so it isn't restated there. Raises
    `TemplateRenderError` on any Jinja2 failure (missing template, missing
    heading block, etc.) instead of letting the exception propagate as-is,
    so every call site's failure path looks the same regardless of which
    template or context field caused it.
    """
    tone = TEMPLATE_TONES.get(template_name, "brand")
    context = {
        **context,
        "tone": tone,
        "t": asdict(TONES[tone]),
        "current_year": datetime.now(UTC).year,
        "logo_src": _logo_src(),
        "staff_portal_url": (settings.staff_portal_url or "").strip() or None,
    }
    try:
        html_template = _html_env.get_template(f"{template_name}.html")
        heading_block = html_template.blocks.get("heading")
        if heading_block is None:
            raise TemplateRenderError(f"Template {template_name!r} declares no heading block")
        # The block renders through HTML autoescaping; a subject header and
        # the plain-text part both need the unescaped text.
        heading = html_unescape(
            " ".join("".join(heading_block(html_template.new_context(context))).split())
        )
        eyebrow_block = html_template.blocks.get("eyebrow")
        eyebrow = (
            html_unescape(
                " ".join("".join(eyebrow_block(html_template.new_context(context))).split())
            )
            if eyebrow_block is not None
            else ""
        )
        html = html_template.render(context)
        text = _text_env.get_template(f"{template_name}.txt").render(
            {**context, "heading": heading, "eyebrow": eyebrow}
        )
    except TemplateError as exc:
        raise TemplateRenderError(str(exc)) from exc
    except Exception as exc:
        # A filter choking on an unexpected value type (e.g. a `str` where a
        # `date` was expected) raises a plain Python error, not a Jinja one;
        # left uncaught it would make the Celery task retry forever instead
        # of taking the spec's plain-text fallback path.
        raise TemplateRenderError(f"{type(exc).__name__}: {exc}") from exc
    # Conditional rows in the text templates leave blank-line runs behind.
    text = _BLANK_LINE_RUNS.sub("\n\n", text).strip() + "\n"
    return RenderedEmail(subject=heading, html=html, text=text)
