"""Fast2SMS WhatsApp template client — the WhatsApp counterpart of
`core/sms.py` (shares its API key, number normaliser and error types).
Business-initiated WhatsApp messages must be approved templates, so there is
no free-text send here either.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

import httpx

from vmss_api.core.config import settings
from vmss_api.core.logging import logger
from vmss_api.core.sms import (
    SmsDispatchError,
    SmsNotConfiguredError,
    mask_phone,
    normalise_indian_mobile,
    sanitise_variable,
)

__all__ = ["Fast2WhatsAppSender", "WhatsAppTemplate"]

_REQUEST_TIMEOUT_SECONDS = 10.0


class WhatsAppTemplate(StrEnum):
    otp = "otp"
    registration_pending = "registration_pending"
    registration_confirmed = "registration_confirmed"
    registration_denied = "registration_denied"
    visit_rescheduled = "visit_rescheduled"
    visit_details_changed = "visit_details_changed"


class Fast2WhatsAppSender:
    async def _upload_png(
        self,
        png: bytes,
        api_key: str,
        phone_number_id: str,
        masked_number: str,
        template: WhatsAppTemplate,
    ) -> str:
        """Uploads the image to the gateway's media store and returns its id —
        no public URL needed, unlike a header `link`.
        """
        url = (
            f"{settings.fast2sms_base_url}/dev/whatsapp/"
            f"{settings.fast2sms_whatsapp_api_version}/{phone_number_id}/media"
        )
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": api_key},
                    data={"messaging_product": "whatsapp", "type": "image/png"},
                    files={"file": ("qr.png", png, "image/png")},
                )
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "fast2sms_whatsapp_media_upload_failed",
                template=template.value,
                identifier=masked_number,
                exception_type=type(exc).__name__,
            )
            raise SmsDispatchError("WhatsApp media upload failed") from exc
        media_id = payload.get("id") if isinstance(payload, dict) else None
        if response.status_code == 200 and media_id:
            return str(media_id)
        logger.warning(
            "fast2sms_whatsapp_media_upload_failed",
            template=template.value,
            identifier=masked_number,
            http_status=response.status_code,
        )
        raise SmsDispatchError("WhatsApp media upload failed")

    async def send(
        self,
        *,
        to: str,
        template: WhatsAppTemplate,
        variables: Sequence[object],
        header_image_png: bytes | None = None,
    ) -> None:
        api_key = settings.fast2sms_api_key
        phone_number_id = settings.fast2sms_whatsapp_phone_number_id
        template_name = getattr(settings, f"fast2sms_whatsapp_template_{template.value}")
        if not api_key or not phone_number_id or not template_name:
            raise SmsNotConfiguredError(
                f"Fast2SMS WhatsApp is not configured for template '{template.value}' — "
                "set FAST2SMS_API_KEY, FAST2SMS_WHATSAPP_PHONE_NUMBER_ID and the template's name"
            )
        if template is WhatsAppTemplate.registration_confirmed and not header_image_png:
            # The approved template has an image header (the QR pass); Meta
            # rejects it without one.
            raise SmsNotConfiguredError("WhatsApp registration_confirmed needs a QR image")
        number = normalise_indian_mobile(to)
        parameters = [
            {"type": "text", "text": sanitise_variable(v, max_length=None)} for v in variables
        ]
        components: list[dict[str, Any]] = []
        if header_image_png:
            media_id = await self._upload_png(
                header_image_png, api_key, phone_number_id, mask_phone(number), template
            )
            components.append(
                {
                    "type": "header",
                    "parameters": [{"type": "image", "image": {"id": media_id}}],
                }
            )
        components.append({"type": "body", "parameters": parameters})
        if template is WhatsAppTemplate.otp:
            # The authentication template also carries the code in its
            # copy-code button; Fast2SMS wants sub_type "url" for that.
            components.append(
                {"type": "button", "sub_type": "url", "index": "0", "parameters": parameters}
            )
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": f"91{number}",
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": settings.fast2sms_whatsapp_language_code},
                "components": components,
            },
        }
        url = (
            f"{settings.fast2sms_base_url}/dev/whatsapp/"
            f"{settings.fast2sms_whatsapp_api_version}/{phone_number_id}/messages"
        )
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=body, headers={"Authorization": api_key})
        except httpx.HTTPError as exc:
            logger.warning(
                "fast2sms_whatsapp_dispatch_failed",
                template=template.value,
                identifier=mask_phone(number),
                exception_type=type(exc).__name__,
            )
            raise SmsDispatchError("WhatsApp dispatch failed") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if response.status_code == 200 and messages and messages[0].get("id"):
            return
        # Only the gateway's own message is logged — a raw body can echo
        # the recipient's full number back.
        error = payload.get("error") if isinstance(payload, dict) else None
        gateway_message = (
            (error.get("message") if isinstance(error, dict) else payload.get("message"))
            if isinstance(payload, dict)
            else None
        )
        logger.warning(
            "fast2sms_whatsapp_dispatch_failed",
            template=template.value,
            identifier=mask_phone(number),
            http_status=response.status_code,
            gateway_message=gateway_message,
        )
        raise SmsDispatchError("WhatsApp dispatch failed")
