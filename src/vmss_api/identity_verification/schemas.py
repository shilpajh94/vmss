from enum import StrEnum
from typing import Self

from email_validator import EmailNotValidError, validate_email
from pydantic import Field, model_validator

from vmss_api.core.schemas import CamelModel


class Channel(StrEnum):
    email = "email"
    sms = "sms"
    whatsapp = "whatsapp"


def _is_valid_email(value: str) -> bool:
    try:
        validate_email(value, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def _is_valid_phone(value: str) -> bool:
    digits = value.removeprefix("+")
    return digits.isdigit() and 7 <= len(digits) <= 15


def _check_identifier_matches_channel(identifier: str, channel: Channel) -> None:
    """spec.md "Identifier does not match the requested channel" — an
    `email` channel requires an email-shaped identifier; `sms`/`whatsapp`
    require a phone-shaped one. Shared by both request/verify schemas below
    so the rule can't drift between the two.
    """
    if channel == Channel.email:
        if not _is_valid_email(identifier):
            raise ValueError("identifier must be a valid email address for channel 'email'")
    elif not _is_valid_phone(identifier):
        raise ValueError("identifier must be a valid phone number for channel 'sms'/'whatsapp'")


class OtpRequestIn(CamelModel):
    identifier: str = Field(max_length=320)
    channel: Channel

    @model_validator(mode="after")
    def _check_identifier(self) -> Self:
        _check_identifier_matches_channel(self.identifier, self.channel)
        return self


class OtpRequestOut(CamelModel):
    identifier: str
    channel: Channel


class OtpVerifyIn(CamelModel):
    identifier: str = Field(max_length=320)
    channel: Channel
    code: str = Field(pattern=r"^\d{4,10}$")

    @model_validator(mode="after")
    def _check_identifier(self) -> Self:
        _check_identifier_matches_channel(self.identifier, self.channel)
        return self


class OtpVerifyOut(CamelModel):
    identifier: str
    channel: Channel
    proof_token: str
