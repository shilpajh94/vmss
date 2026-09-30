"""Email/SMS/WhatsApp dispatch for `identity_verification` only — mirrors,
does not import, `invitations/notifications.py`'s pattern. See
`add-identity-verification-otp/design.md`'s Non-Goals for why these two
near-identical sender abstractions aren't merged into a shared
`notifications/` package yet.
"""

from typing import Protocol

import aiosmtplib
import anyio
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from vmss_api.core.config import settings
from vmss_api.core.emailing import build_message
from vmss_api.core.logging import logger
from vmss_api.identity_verification.masking import mask_identifier


class EmailSender(Protocol):
    async def send(
        self, *, to: str, subject: str, body: str, html_body: str | None = None
    ) -> None: ...


class SmsSender(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...


class WhatsAppSender(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...


class GatewayNotConfiguredError(RuntimeError):
    """No gateway is configured for this channel in the current deployment
    — raised rather than swallowed, so the caller fails loudly instead of a
    false success (spec.md "OTP delivery over an unconfigured channel
    fails loudly").
    """


class SmsDispatchError(RuntimeError):
    """A *configured* SMS gateway (Twilio) rejected or failed to send the
    message — a transient/operational failure, distinct from
    `GatewayNotConfiguredError`'s "nothing is set up." design.md's
    Idempotency-Key refinement treats the two differently: this one is
    never cached as an idempotent response, so a retry re-attempts dispatch.
    """


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


class UnconfiguredSmsSender:
    async def send(self, *, to: str, body: str) -> None:
        raise GatewayNotConfiguredError(
            "No SMS gateway is configured — set TWILIO_ACCOUNT_SID/"
            "TWILIO_AUTH_TOKEN/TWILIO_SMS_FROM_NUMBER to enable SMS delivery"
        )


class UnconfiguredWhatsAppSender:
    async def send(self, *, to: str, body: str) -> None:
        raise GatewayNotConfiguredError(
            "No WhatsApp gateway is configured — see design.md's Non-Goals"
        )


class TwilioSmsSender:
    """Real SMS delivery via Twilio (design.md's Senders decision — chosen
    as a mainstream, well-documented default since no vendor preference
    was given).
    """

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self._client = TwilioClient(account_sid, auth_token)
        self._from_number = from_number

    async def send(self, *, to: str, body: str) -> None:
        def _send_sync() -> None:
            self._client.messages.create(to=to, from_=self._from_number, body=body)

        try:
            # `Client.messages.create` is a blocking network call — the
            # Twilio SDK has no async client, so this runs off the event
            # loop rather than blocking every concurrent request for the
            # duration of the round-trip (fastapi-architecture.md §4).
            await anyio.to_thread.run_sync(_send_sync)
        except TwilioRestException as exc:
            logger.warning(
                "twilio_sms_dispatch_failed",
                identifier=mask_identifier(to),
                twilio_error_code=exc.code,
                twilio_message=exc.msg,
            )
            raise SmsDispatchError("SMS dispatch failed") from exc


email_sender: EmailSender = SmtpEmailSender()
whatsapp_sender: WhatsAppSender = UnconfiguredWhatsAppSender()

_twilio_configured = bool(
    settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_sms_from_number
)
sms_sender: SmsSender = (
    TwilioSmsSender(
        settings.twilio_account_sid,  # type: ignore[arg-type]
        settings.twilio_auth_token,  # type: ignore[arg-type]
        settings.twilio_sms_from_number,  # type: ignore[arg-type]
    )
    if _twilio_configured
    else UnconfiguredSmsSender()
)
