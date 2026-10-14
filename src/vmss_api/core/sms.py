"""Fast2SMS DLT SMS client, shared by `identity_verification` (OTP) and
`invitations` (lifecycle notifications) — lives in `core/` so neither feature
imports the other. Every message is template-driven: India's DLT rules only
allow pre-registered templates, so there is deliberately no free-text send.
"""

import re
from collections.abc import Sequence
from enum import StrEnum

import httpx

from vmss_api.core.config import settings
from vmss_api.core.logging import logger

__all__ = [
    "Fast2SmsSender",
    "SmsDispatchError",
    "SmsInvalidNumberError",
    "SmsNotConfiguredError",
    "SmsTemplate",
    "mask_phone",
    "normalise_indian_mobile",
    "sanitise_variable",
]

# DLT caps a template variable's length.
MAX_VARIABLE_LENGTH = 30
_REQUEST_TIMEOUT_SECONDS = 10.0


class SmsTemplate(StrEnum):
    otp = "otp"
    registration_pending = "registration_pending"
    registration_confirmed = "registration_confirmed"
    registration_confirmed_code = "registration_confirmed_code"
    registration_denied = "registration_denied"
    visit_rescheduled = "visit_rescheduled"
    visit_details_changed = "visit_details_changed"


class SmsNotConfiguredError(RuntimeError):
    """Key, sender ID or the template's ID is blank — raised rather than
    swallowed so the caller fails loudly instead of a false success.
    """


class SmsDispatchError(RuntimeError):
    """A *configured* gateway rejected or failed to send the message — a
    transient/operational failure, distinct from `SmsNotConfiguredError`.
    """


class SmsInvalidNumberError(SmsDispatchError):
    """The recipient can't be normalised to a valid mobile number. Not worth
    retrying — the same number will fail the same way.
    """


def mask_phone(number: str) -> str:
    return f"***{number[-2:]}" if len(number) >= 2 else "***"


def normalise_indian_mobile(number: str) -> str:
    """Returns the bare 10-digit form from `+91…`, `91…`, `0…` or bare input."""
    digits = re.sub(r"[\s\-()]", "", number)
    digits = digits.removeprefix("+")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise SmsInvalidNumberError("Recipient is not a valid Indian mobile number")
    return digits


def sanitise_variable(value: object, *, max_length: int | None = MAX_VARIABLE_LENGTH) -> str:
    """Stringifies a template variable, removing characters that would break
    the `|`-joined list or the template (separator, newlines).
    """
    text = str(value).replace("|", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length] if max_length is not None else text


class Fast2SmsSender:
    async def send(self, *, to: str, template: SmsTemplate, variables: Sequence[object]) -> None:
        api_key = settings.fast2sms_api_key
        sender_id = settings.fast2sms_sender_id
        template_id = getattr(settings, f"fast2sms_template_{template.value}")
        if not api_key or not sender_id or not template_id:
            raise SmsNotConfiguredError(
                f"Fast2SMS SMS is not configured for template '{template.value}' — "
                "set FAST2SMS_API_KEY, FAST2SMS_SENDER_ID and the template's ID"
            )
        number = normalise_indian_mobile(to)
        params = {
            "route": "dlt",
            "sender_id": sender_id,
            "message": template_id,
            "variables_values": "|".join(sanitise_variable(v) for v in variables),
            "numbers": number,
        }
        status_code: int | None = None
        gateway_message: str | None = None
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{settings.fast2sms_base_url}/dev/bulkV2",
                    params=params,
                    headers={"Authorization": api_key},
                )
            status_code = response.status_code
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            gateway_message = str(payload.get("message", response.text[:200]))
            if status_code == 200 and payload.get("return") is True:
                return
        except httpx.HTTPError as exc:
            logger.warning(
                "fast2sms_sms_dispatch_failed",
                template=template.value,
                identifier=mask_phone(number),
                exception_type=type(exc).__name__,
            )
            raise SmsDispatchError("SMS dispatch failed") from exc
        logger.warning(
            "fast2sms_sms_dispatch_failed",
            template=template.value,
            identifier=mask_phone(number),
            http_status=status_code,
            gateway_message=gateway_message,
        )
        raise SmsDispatchError("SMS dispatch failed")
