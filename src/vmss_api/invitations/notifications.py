"""Email/SMS/WhatsApp dispatch for `invitations` only (design.md's "Non-Goals": this
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

from vmss_api.core.emailing import (
    Attachment,
    EmailSender,
    InlineImage,
    SmtpEmailSender,
    make_attachment,
    make_inline_image,
)
from vmss_api.core.sms import Fast2SmsSender
from vmss_api.core.whatsapp import Fast2WhatsAppSender

__all__ = [
    "Attachment",
    "EmailSender",
    "InlineImage",
    "make_attachment",
    "make_inline_image",
    "email_sender",
    "sms_sender",
    "whatsapp_sender",
]

email_sender: EmailSender = SmtpEmailSender()
sms_sender = Fast2SmsSender()
whatsapp_sender = Fast2WhatsAppSender()
