"""OTP generation/verification for `identity_verification` (API-15).

Redis-only state — see `add-identity-verification-otp/design.md`'s "New
standalone feature package, Redis-only" decision. No repository/model
layer exists here on purpose: an OTP attempt has no durable audit/business
value once it expires or is consumed.
"""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

from vmss_api.core.config import settings
from vmss_api.core.email_rendering import TemplateRenderError, render_email
from vmss_api.core.logging import logger
from vmss_api.core.redis import get_redis
from vmss_api.core.security import create_identity_verified_token
from vmss_api.identity_verification import senders
from vmss_api.identity_verification.masking import mask_identifier
from vmss_api.identity_verification.schemas import Channel


class PerIdentifierRateLimitExceeded(Exception):
    """An identifier — not just an IP — has exceeded the configured OTP
    request rate (design.md's per-identifier rate limiting decision: an
    attacker rotating source IPs must not be able to bomb one phone
    number/email indefinitely).
    """


class InvalidOrExpiredCode(Exception):
    """Generic verification failure — covers a missing/expired code, an
    already-exhausted code, and a wrong code, all deliberately
    indistinguishable to the caller (spec.md: never reveal which part of
    the submission was wrong).
    """


@dataclass
class OtpDispatchResult:
    identifier: str
    channel: Channel


@dataclass
class OtpVerifyResult:
    identifier: str
    channel: Channel
    proof_token: str


def _otp_key(tenant_id: uuid.UUID, channel: Channel, identifier: str) -> str:
    return f"vmss:{tenant_id}:identity-verification:otp:{channel.value}:{identifier}"


def _rate_limit_key(tenant_id: uuid.UUID, channel: Channel, identifier: str) -> str:
    return f"vmss:{tenant_id}:identity-verification:rl:{channel.value}:{identifier}"


def _hash_code(code: str) -> str:
    # HMAC-SHA256, not Argon2 — a numeric code has far less entropy than a
    # password, and the failed-attempt cap plus rate limiting (not hash
    # cost) is what actually blocks brute force here (design.md's "Redis
    # key shape" decision).
    return hmac.new(settings.jwt_secret_key.encode(), code.encode(), hashlib.sha256).hexdigest()


def _generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))


async def _check_rate_limit(tenant_id: uuid.UUID, channel: Channel, identifier: str) -> None:
    redis = await get_redis()
    key = _rate_limit_key(tenant_id, channel, identifier)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.otp_rate_limit_window_seconds)
    if count > settings.otp_rate_limit_per_identifier:
        raise PerIdentifierRateLimitExceeded(mask_identifier(identifier))


async def request_otp(
    *, tenant_id: uuid.UUID, identifier: str, channel: Channel
) -> OtpDispatchResult:
    """Generates and dispatches a fresh code, superseding any code already
    outstanding for this identifier — the plain overwrite below achieves
    "at most one valid code per identifier" (spec.md) with no separate
    invalidation step.
    """
    await _check_rate_limit(tenant_id, channel, identifier)

    code = _generate_code()
    key = _otp_key(tenant_id, channel, identifier)
    redis = await get_redis()
    await redis.hset(
        key,
        mapping={"code_hash": _hash_code(code), "attempts_remaining": settings.otp_max_attempts},
    )
    await redis.expire(key, settings.otp_ttl_seconds)

    minutes = settings.otp_ttl_seconds // 60
    body = f"Your verification code is {code}. It expires in {minutes} minutes."
    if channel == Channel.email:
        subject, text_body, html_body = "Your verification code", body, None
        try:
            rendered = render_email("verification_code", {"code": code, "minutes": minutes})
            subject, text_body, html_body = rendered.subject, rendered.text, rendered.html
        except TemplateRenderError:
            # The one-line body is the fallback; the code itself is never
            # logged (identity-verification "OTP codes ... are never exposed
            # in plaintext outside delivery").
            logger.error("email_template_render_failed", template_name="verification_code")
        await senders.email_sender.send(
            to=identifier, subject=subject, body=text_body, html_body=html_body
        )
    elif channel == Channel.sms:
        await senders.sms_sender.send(to=identifier, body=body)
    else:
        await senders.whatsapp_sender.send(to=identifier, body=body)

    logger.info("otp_requested", channel=channel.value, identifier=mask_identifier(identifier))
    return OtpDispatchResult(identifier=identifier, channel=channel)


async def verify_otp(
    *, tenant_id: uuid.UUID, identifier: str, channel: Channel, code: str
) -> OtpVerifyResult:
    redis = await get_redis()
    key = _otp_key(tenant_id, channel, identifier)
    stored = await redis.hgetall(key)

    if not stored or int(stored.get("attempts_remaining", 0)) <= 0:
        logger.warning(
            "otp_verify_failed", channel=channel.value, identifier=mask_identifier(identifier)
        )
        raise InvalidOrExpiredCode()

    if not hmac.compare_digest(str(stored["code_hash"]), _hash_code(code)):
        remaining = int(stored["attempts_remaining"]) - 1
        if remaining <= 0:
            await redis.delete(key)
        else:
            await redis.hset(key, "attempts_remaining", remaining)
        logger.warning(
            "otp_verify_failed", channel=channel.value, identifier=mask_identifier(identifier)
        )
        raise InvalidOrExpiredCode()

    await redis.delete(key)  # single-use — a verified code cannot be replayed
    proof_token = create_identity_verified_token(identifier, channel.value, tenant_id)
    logger.info("otp_verified", channel=channel.value, identifier=mask_identifier(identifier))
    return OtpVerifyResult(identifier=identifier, channel=channel, proof_token=proof_token)
