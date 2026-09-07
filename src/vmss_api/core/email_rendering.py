"""Jinja2-based HTML email rendering (role-based-invitation-workflow,
`email-notifications` capability). Replaces the plain `f-string` bodies
`invitations/tasks.py` used to build directly — a rendering step in front of
the existing `EmailSender` interface (`core/emailing.py`), not a parallel
dispatch path, so a provider swap never has to touch template code.

Templates live in `core/email_templates/` as HTML files extending
`base.html` (the shared branded layout — logo, header, footer). Each
template defines a `subject` block (rendered separately, so a caller gets
the subject line without parsing it back out of the HTML) and a `content`
block for its body.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

_TEMPLATES_DIR = Path(__file__).parent / "email_templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


class TemplateRenderError(RuntimeError):
    """Raised when a named template fails to render for any reason. Callers
    (`invitations/tasks.py`) catch this and fall back to a minimal
    plain-text email — spec.md "Template Rendering Failure Falls Back to a
    Minimal Plain-Text Email" — rather than failing to send anything at all.
    """


def render_email_html(template_name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Renders `<template_name>.html`, returning `(subject, html_body)`.
    Raises `TemplateRenderError` on any Jinja2 failure (missing template,
    undefined-variable error, etc.) instead of letting the exception
    propagate as-is, so every call site's failure path looks the same
    regardless of which template or context field caused it.
    """
    try:
        template = _env.get_template(f"{template_name}.html")
        subject_block = template.blocks.get("subject")
        if subject_block is None:
            raise TemplateRenderError(f"Template {template_name!r} declares no subject block")
        ctx = template.new_context(context)
        subject = "".join(subject_block(ctx)).strip()
        html_body = template.render(context)
        return subject, html_body
    except TemplateError as exc:
        raise TemplateRenderError(str(exc)) from exc
