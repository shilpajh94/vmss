"""Email/SMS dispatch for `invitations` only (design.md's "Non-Goals": this
is not the general multi-channel `notifications/` package `project-rules.md`
describes — that gets built once a second feature needs it,
`background-jobs.md` §1). Only ever called from `invitations/tasks.py`, never
from `router.py`/`service.py` directly (`background-jobs.md` §5).
"""

from email.message import EmailMessage
from typing import Protocol

import aiosmtplib

from vmss_api.core.config import settings


class Attachment(Protocol):
    content: bytes
    filename: str
    mime_type: str


class EmailSender(Protocol):
    async def send(
        self, *, to: str, subject: str, body: str, attachment: "Attachment | None" = None
    ) -> None: ...


class SmsSender(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...


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
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls,
        )


class SmsGatewayNotConfiguredError(RuntimeError):
    """No SMS gateway has been chosen yet (design.md Open Questions). Raised
    rather than swallowed, so a task dispatching to SMS fails loudly through
    Celery's normal retry/exhaustion-logging path (`background-jobs.md` §4)
    instead of silently pretending to succeed.
    """


class UnconfiguredSmsSender:
    async def send(self, *, to: str, body: str) -> None:
        raise SmsGatewayNotConfiguredError(
            "No SMS gateway is configured — see design.md's Open Questions"
        )


email_sender: EmailSender = SmtpEmailSender()
sms_sender: SmsSender = UnconfiguredSmsSender()
