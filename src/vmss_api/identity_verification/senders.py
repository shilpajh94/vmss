"""Email/SMS/WhatsApp dispatch for `identity_verification` only — mirrors,
does not import, `invitations/notifications.py`'s pattern. See
`add-identity-verification-otp/design.md`'s Non-Goals for why these two
near-identical sender abstractions aren't merged into a shared
`notifications/` package yet.
"""

from collections.abc import Sequence
from typing import Protocol

import aiosmtplib

from vmss_api.core.config import settings
from vmss_api.core.emailing import build_message
from vmss_api.core.logging import logger
from vmss_api.core.sms import Fast2SmsSender, SmsNotConfiguredError, SmsTemplate
from vmss_api.core.sms import SmsDispatchError as SmsDispatchError
from vmss_api.core.whatsapp import Fast2WhatsAppSender, WhatsAppTemplate
from vmss_api.identity_verification.masking import mask_identifier


class EmailSender(Protocol):
    async def send(
        self, *, to: str, subject: str, body: str, html_body: str | None = None
    ) -> None: ...


class SmsSender(Protocol):
    async def send(
        self, *, to: str, template: SmsTemplate, variables: Sequence[object]
    ) -> None: ...


class WhatsAppSender(Protocol):
    async def send(
        self, *, to: str, template: WhatsAppTemplate, variables: Sequence[object]
    ) -> None: ...


# "Nothing is set up" (spec "OTP delivery over an unconfigured channel fails
# loudly") and "a configured gateway failed" (never idempotency-cached) are
# the shared `core/sms.py` errors, re-exported under the names the router
# already catches.
GatewayNotConfiguredError = SmsNotConfiguredError


class EmailDispatchError(RuntimeError):
    """Same category as `SmsDispatchError`, for the SMTP channel — a
    configured mail server that's unreachable or rejected the message,
    not a missing-configuration case.
    """


class SmtpEmailSender:
    """Same `aiosmtplib`/`settings.smtp_*` approach as `core/emailing.py`,
    and builds its message with that module's `build_message` (so the
    templated verification email gets the same From name and inline Visimio
    logo as every other email — refine-email-templates-and-visimio-brand).
    Kept as its own sender rather than re-exporting the core one because
    this flow needs `EmailDispatchError` (never cached as an idempotent
    response) and masked-identifier logging.
    """

    async def send(self, *, to: str, subject: str, body: str, html_body: str | None = None) -> None:
        message = build_message(to=to, subject=subject, body=body, html_body=html_body)
        # aiosmtplib attempts an AUTH login the moment `username` is a
        # non-None value, including an empty string — which an env var set
        # to `SMTP_USERNAME=` (present-but-blank, not absent) produces. The
        # local dev mail-catcher (mailhog/mailpit) doesn't support AUTH, so
        # an empty-but-set credential must be treated the same as unset —
        # same fix as `invitations/notifications.py::SmtpEmailSender.send`.
        username = settings.smtp_username or None
        password = settings.smtp_password or None
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=username,
                password=password,
                start_tls=settings.smtp_use_tls,
            )
        except aiosmtplib.SMTPException as exc:
            logger.warning(
                "smtp_email_dispatch_failed",
                identifier=mask_identifier(to),
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                exception_type=type(exc).__name__,
                error=str(exc),
            )
            raise EmailDispatchError("Email dispatch failed") from exc


email_sender: EmailSender = SmtpEmailSender()
sms_sender: SmsSender = Fast2SmsSender()
whatsapp_sender: WhatsAppSender = Fast2WhatsAppSender()
