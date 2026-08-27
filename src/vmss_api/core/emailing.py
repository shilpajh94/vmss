"""Shared SMTP-sending primitive (add-background-jobs-and-integration-tests
design.md Decision 4). Extracted out of `invitations/notifications.py` so
`reports/tasks.py` doesn't duplicate the `aiosmtplib` call — the two
features have nothing else in common (no shared template/multi-channel
abstraction), so this stays a plain sender, not a `notifications/` package.
"""

from email.message import EmailMessage
from typing import Protocol

import aiosmtplib

from vmss_api.core.config import settings
from vmss_api.core.logging import logger


class Attachment(Protocol):
    content: bytes
    filename: str
    mime_type: str


class EmailSender(Protocol):
    async def send(
        self, *, to: str, subject: str, body: str, attachment: "Attachment | None" = None
    ) -> None: ...


class _Attachment:
    def __init__(self, content: bytes, filename: str, mime_type: str) -> None:
        self.content = content
        self.filename = filename
        self.mime_type = mime_type


def make_attachment(content: bytes, filename: str, mime_type: str) -> _Attachment:
    return _Attachment(content, filename, mime_type)


class SmtpEmailSender:
    """Design.md Decision 4 — SMTP against whatever mail server `settings`
    points at (a local dev mail-catcher by default). Swapping to a
    transactional-email provider's API later is a new `EmailSender`
    implementation, not a call-site change.
    """

    async def send(
        self, *, to: str, subject: str, body: str, attachment: "Attachment | None" = None
    ) -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if attachment is not None:
            maintype, _, subtype = attachment.mime_type.partition("/")
            message.add_attachment(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )
        # aiosmtplib attempts an AUTH login the moment `username` is a
        # non-None value, including an empty string — which an env var set
        # to `SMTP_USERNAME=` (present-but-blank, not absent) produces. The
        # local dev mail-catcher (mailhog/mailpit) doesn't support AUTH, so
        # an empty-but-set credential must be treated the same as unset.
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
            # No recipient address here — the enqueuing task already binds
            # tenant/invitation context (logging-observability.md §2), and
            # that's enough to locate the record without logging PII.
            logger.warning(
                "smtp_email_dispatch_failed",
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                exception_type=type(exc).__name__,
                error=str(exc),
            )
            raise


email_sender: EmailSender = SmtpEmailSender()
