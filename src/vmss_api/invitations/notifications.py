"""Email/SMS dispatch for `invitations` only (design.md's "Non-Goals": this
is not the general multi-channel `notifications/` package `project-rules.md`
describes — that gets built once a second feature needs it,
`background-jobs.md` §1). Only ever called from `invitations/tasks.py`, never
from `router.py`/`service.py` directly (`background-jobs.md` §5).

The SMTP-sending primitive itself lives in `core/emailing.py` — shared with
`reports/tasks.py`'s scheduled snapshot job
(add-background-jobs-and-integration-tests design.md Decision 4) — and is
re-exported here so this module's existing call sites
(`notifications.email_sender`, `notifications.make_attachment`) don't need
to change.
"""

from typing import Protocol

from vmss_api.core.emailing import Attachment, EmailSender, SmtpEmailSender, make_attachment

__all__ = [
    "Attachment",
    "EmailSender",
    "SmsSender",
    "make_attachment",
    "SmsGatewayNotConfiguredError",
    "UnconfiguredSmsSender",
    "email_sender",
    "sms_sender",
]


class SmsSender(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...


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
