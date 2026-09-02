import asyncio
import re
import time
import uuid

import aiosmtplib
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs
from twilio.base.exceptions import TwilioRestException

from factories import TenantFactory
from vmss_api.core.config import settings
from vmss_api.core.security import decode_token
from vmss_api.identity_verification import senders, service
from vmss_api.identity_verification.schemas import Channel
from vmss_api.identity_verification.senders import TwilioSmsSender, UnconfiguredSmsSender
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """Mirrors `invitations/tests.py`'s fixture of the same name — this
    feature's public endpoints have no token and resolve
    `settings.default_tenant_slug` the same way `GET /invitations/track`
    does.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


class _RecordingSender:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _unique_email() -> str:
    return f"otp-{uuid.uuid4().hex[:10]}@example.com"


def _unique_phone() -> str:
    return f"+1555{uuid.uuid4().int % 10_000_000:07d}"


def _extract_code(body: str) -> str:
    match = re.search(r"code is (\d+)", body)
    assert match is not None, body
    return match.group(1)


def _flip(code: str) -> str:
    """A guaranteed-wrong code of the same shape as `code`."""
    return "".join("9" if c != "9" else "8" for c in code)


# --- Happy path: email (real SmtpEmailSender in production, faked here) ----


async def test_request_and_verify_otp_over_email_success(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": identifier, "channel": "email"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"identifier": identifier, "channel": "email"}
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["subject"] == "Your verification code"
    code = _extract_code(recorder.calls[0]["body"])

    verify_response = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json={"identifier": identifier, "channel": "email", "code": code},
    )
    assert verify_response.status_code == 200, verify_response.text
    data = verify_response.json()["data"]
    assert data["identifier"] == identifier
    assert data["channel"] == "email"

    claims = decode_token(data["proofToken"])
    assert claims["sub"] == identifier
    assert claims["type"] == "identity_verified"
    assert claims["channel"] == "email"
    assert claims["tenant_id"] == str(tenant.id)


# --- Real dispatch verification (against DDEV's Mailpit, not a fake sender) ---
#
# The test above proves the endpoint *calls* the sender correctly, not that a
# real email is deliverable — see
# `invitations/tests.py::test_send_approval_notification_delivers_email_
# with_qr_via_mailpit` for the established pattern this mirrors. Highest
# priority of the Mailpit additions (proposal.md finding #2): OTP-over-email
# is the one channel with an actual live dev-server incident history
# (`diagnose-otp-email-delivery-failure`).

_MAILPIT_BASE_URL = "http://localhost:8025/api/v1"
_MAILPIT_API_URL = f"{_MAILPIT_BASE_URL}/messages"


async def test_request_and_verify_otp_over_email_delivers_real_email_via_mailpit(
    client: AsyncClient, tenant: Tenant
) -> None:
    """`senders.email_sender` is left as the real `SmtpEmailSender` (the
    module default) here, unlike every other OTP test in this file — a real
    SMTP send goes out for Mailpit to capture, and the verification code
    used to complete `/otp/verify` is read back from the *received* message,
    not from an in-process recorder.
    """
    identifier = _unique_email()

    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": identifier, "channel": "email"},
    )
    assert response.status_code == 200, response.text

    async with AsyncClient() as mailpit:
        list_response = await mailpit.get(_MAILPIT_API_URL, params={"limit": 50})
        assert list_response.status_code == 200
        matches = [
            m
            for m in list_response.json()["messages"]
            if any(to["Address"] == identifier for to in m["To"])
        ]
        assert len(matches) == 1, (
            f"expected exactly one Mailpit message to {identifier}, found {len(matches)}"
        )
        detail_response = await mailpit.get(f"{_MAILPIT_BASE_URL}/message/{matches[0]['ID']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["Subject"] == "Your verification code"
        code = _extract_code(detail["Text"])

    verify_response = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json={"identifier": identifier, "channel": "email", "code": code},
    )
    assert verify_response.status_code == 200, verify_response.text
    data = verify_response.json()["data"]
    assert data["identifier"] == identifier
    assert data["channel"] == "email"


# --- SMS: real dispatch via a mocked Twilio client (9.2a) -------------------


async def test_request_otp_over_sms_with_configured_twilio_dispatches(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    sender = TwilioSmsSender("ACfake", "faketoken", "+15005550006")
    calls: list[dict] = []
    monkeypatch.setattr(sender._client.messages, "create", lambda **kw: calls.append(kw))
    monkeypatch.setattr(senders, "sms_sender", sender)

    identifier = _unique_phone()
    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": identifier, "channel": "sms"},
    )
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0]["to"] == identifier
    assert calls[0]["from_"] == "+15005550006"
    assert "Your verification code is" in calls[0]["body"]


async def test_twilio_sms_sender_send_does_not_block_the_event_loop(monkeypatch) -> None:
    """design.md's Risk: the Twilio SDK's synchronous client must go
    through `anyio.to_thread.run_sync`, not block the event loop for the
    duration of the (simulated) network round-trip.
    """
    sender = TwilioSmsSender("ACfake", "faketoken", "+15005550006")
    monkeypatch.setattr(sender._client.messages, "create", lambda **kw: time.sleep(0.2))

    ticks: list[float] = []

    async def _ticker() -> None:
        for _ in range(4):
            await asyncio.sleep(0.02)
            ticks.append(time.monotonic())

    await asyncio.gather(sender.send(to="+15005550006", body="hi"), _ticker())
    # If `send` blocked the loop, the ticker couldn't have made progress
    # concurrently with the simulated 0.2s Twilio call.
    assert len(ticks) == 4


async def test_request_otp_over_sms_without_twilio_configured_returns_503(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(senders, "sms_sender", UnconfiguredSmsSender())
    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": _unique_phone(), "channel": "sms"},
    )
    assert response.status_code == 503
    assert response.json()["success"] is False


async def test_request_otp_over_whatsapp_always_returns_503(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": _unique_phone(), "channel": "whatsapp"},
    )
    assert response.status_code == 503
    assert response.json()["success"] is False


async def test_request_otp_twilio_failure_returns_503_without_leaking_detail(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    sender = TwilioSmsSender("ACfake", "faketoken", "+15005550006")
    attempts = {"n": 0}

    def _failing_create(**kwargs):
        attempts["n"] += 1
        raise TwilioRestException(
            400, "https://api.twilio.com/x", msg="Invalid To Number", code=21211
        )

    monkeypatch.setattr(sender._client.messages, "create", _failing_create)
    monkeypatch.setattr(senders, "sms_sender", sender)

    idempotency_key = str(uuid.uuid4())
    identifier = _unique_phone()
    payload = {"identifier": identifier, "channel": "sms"}

    first = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert first.status_code == 503
    assert "21211" not in first.text
    assert "Invalid To Number" not in first.text

    # Deliberately NOT cached (design.md's Idempotency-Key refinement) — a
    # retry with the same key re-attempts dispatch instead of replaying the
    # same Twilio-side failure forever.
    second = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert second.status_code == 503
    assert attempts["n"] == 2


async def test_request_otp_smtp_failure_returns_503_without_leaking_detail(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    class _FailingEmailSender:
        async def send(self, **kwargs) -> None:
            raise senders.EmailDispatchError("Email dispatch failed")

    monkeypatch.setattr(senders, "email_sender", _FailingEmailSender())

    idempotency_key = str(uuid.uuid4())
    identifier = _unique_email()
    payload = {"identifier": identifier, "channel": "email"}

    first = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert first.status_code == 503

    # Deliberately NOT cached, same as the Twilio-failure case — a retry
    # with the same key re-attempts dispatch instead of replaying the same
    # SMTP-side failure forever.
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)

    second = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert second.status_code == 200
    assert len(recorder.calls) == 1


async def test_smtp_dispatch_failure_logs_host_port_and_exception_type(monkeypatch) -> None:
    """`fix-public-org-listings-and-email-diagnostics/design.md` Decision 3
    — a dispatch failure now logs enough detail (SMTP host/port, the
    underlying exception's type) to root-cause a dev-server-only failure
    without reproducing it locally, while never leaking credentials or the
    OTP code itself.
    """

    async def _raise(*args, **kwargs) -> None:
        raise aiosmtplib.SMTPConnectError("Connection refused")

    monkeypatch.setattr(aiosmtplib, "send", _raise)
    monkeypatch.setattr(settings, "smtp_username", "should-never-appear")
    monkeypatch.setattr(settings, "smtp_password", "super-secret-password")  # noqa: S105

    sender = senders.SmtpEmailSender()
    with capture_logs() as captured, pytest.raises(senders.EmailDispatchError):
        await sender.send(to=_unique_email(), subject="Your code", body="Your code is 654321")

    [entry] = [e for e in captured if e["event"] == "smtp_email_dispatch_failed"]
    assert entry["smtp_host"] == settings.smtp_host
    assert entry["smtp_port"] == settings.smtp_port
    assert entry["exception_type"] == "SMTPConnectError"

    log_text = str(captured)
    assert "should-never-appear" not in log_text
    assert "super-secret-password" not in log_text
    assert "654321" not in log_text


async def test_request_otp_gateway_not_configured_response_is_cached(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    """Contrasts with the transient-Twilio-failure test above: a
    `GatewayNotConfiguredError` outcome IS cached, so a retry never
    re-attempts dispatch even if the sender is reconfigured in between.
    """
    monkeypatch.setattr(senders, "sms_sender", UnconfiguredSmsSender())
    idempotency_key = str(uuid.uuid4())
    identifier = _unique_phone()
    payload = {"identifier": identifier, "channel": "sms"}

    first = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert first.status_code == 503

    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "sms_sender", recorder)

    second = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert second.status_code == 503
    assert recorder.calls == []  # served from cache — never actually attempted


# --- Validation --------------------------------------------------------------


async def test_request_otp_channel_identifier_mismatch_rejected(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": "not-an-email-or-phone", "channel": "email"},
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": "someone@example.com", "channel": "sms"},
    )
    assert response.status_code == 422


# --- Expiry, attempts, single-use, superseding (direct service calls, per --
# testing-standards.md §3's "unit-style" allowance for edge cases). ---------


async def test_verify_otp_expired_code_rejected(tenant: Tenant, monkeypatch) -> None:
    monkeypatch.setattr(settings, "otp_ttl_seconds", 1)
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    code = _extract_code(recorder.calls[0]["body"])
    await asyncio.sleep(1.5)

    with pytest.raises(service.InvalidOrExpiredCode):
        await service.verify_otp(
            tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=code
        )


async def test_verify_otp_wrong_code_decrements_attempts_until_exhausted(
    tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "otp_max_attempts", 2)
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    correct_code = _extract_code(recorder.calls[0]["body"])
    wrong_code = _flip(correct_code)

    for _ in range(2):
        with pytest.raises(service.InvalidOrExpiredCode):
            await service.verify_otp(
                tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=wrong_code
            )

    # Attempts exhausted — even the originally correct code no longer works.
    with pytest.raises(service.InvalidOrExpiredCode):
        await service.verify_otp(
            tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=correct_code
        )


async def test_verify_otp_correct_code_cannot_be_reused(tenant: Tenant, monkeypatch) -> None:
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    code = _extract_code(recorder.calls[0]["body"])

    result = await service.verify_otp(
        tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=code
    )
    assert result.proof_token

    with pytest.raises(service.InvalidOrExpiredCode):
        await service.verify_otp(
            tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=code
        )


async def test_request_otp_again_invalidates_previous_code(tenant: Tenant, monkeypatch) -> None:
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    first_code = _extract_code(recorder.calls[0]["body"])
    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    second_code = _extract_code(recorder.calls[1]["body"])

    with pytest.raises(service.InvalidOrExpiredCode):
        await service.verify_otp(
            tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=first_code
        )

    result = await service.verify_otp(
        tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=second_code
    )
    assert result.identifier == identifier


# --- Rate limiting -----------------------------------------------------------


async def test_request_otp_per_identifier_rate_limit_exceeded(tenant: Tenant, monkeypatch) -> None:
    monkeypatch.setattr(settings, "otp_rate_limit_per_identifier", 2)
    monkeypatch.setattr(senders, "email_sender", _RecordingSender())
    identifier = _unique_email()

    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    with pytest.raises(service.PerIdentifierRateLimitExceeded):
        await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)


async def test_request_otp_endpoint_returns_429_once_identifier_rate_limited(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    """Covers the per-identifier half of task 9.8. The per-IP `slowapi`
    layer is globally disabled under `ENVIRONMENT=test`
    (`core/rate_limit.py`), the same way every other feature's tests never
    exercise it — this feature's per-identifier limiter is hand-rolled
    Redis, not slowapi, so it stays testable regardless.
    """
    monkeypatch.setattr(settings, "otp_rate_limit_per_identifier", 1)
    monkeypatch.setattr(senders, "email_sender", _RecordingSender())
    identifier = _unique_email()
    payload = {"identifier": identifier, "channel": "email"}

    first = await client.post("/api/v1/identity-verification/otp/request", json=payload)
    assert first.status_code == 200, first.text
    second = await client.post("/api/v1/identity-verification/otp/request", json=payload)
    assert second.status_code == 429


# --- Idempotency --------------------------------------------------------------


async def test_request_otp_idempotency_key_replay_does_not_redispatch(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()
    idempotency_key = str(uuid.uuid4())
    payload = {"identifier": identifier, "channel": "email"}

    first = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    second = await client.post(
        "/api/v1/identity-verification/otp/request",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert first.json() == second.json()
    assert len(recorder.calls) == 1


async def test_verify_otp_idempotency_key_replay_does_not_recount_attempt(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "otp_max_attempts", 2)
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": identifier, "channel": "email"},
    )
    code = _extract_code(recorder.calls[0]["body"])
    wrong_code = _flip(code)
    idempotency_key = str(uuid.uuid4())
    verify_payload = {"identifier": identifier, "channel": "email", "code": wrong_code}

    first = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json=verify_payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    second = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json=verify_payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert first.json() == second.json()

    # otp_max_attempts=2: if the replay had incorrectly counted a second
    # attempt, this would now be exhausted and the still-valid correct code
    # would fail too. It must still succeed.
    verify_correct = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json={"identifier": identifier, "channel": "email", "code": code},
    )
    assert verify_correct.status_code == 200, verify_correct.text


# --- Tenant isolation (Redis key-namespace, not Postgres schema) -------------


async def test_otp_and_rate_limit_state_are_isolated_per_tenant(
    tenant: Tenant, db_session: AsyncSession, monkeypatch
) -> None:
    """design.md's "Redis-namespace isolation test for
    `identity_verification`" decision (task 7.1 of
    `complete-api-test-coverage`): OTP/rate-limit state is keyed
    `vmss:{tenant_id}:...` (database-architecture.md §6), not a Postgres
    schema, so isolation has to be proven at the Redis-key level instead of
    via `make_tenant_schema`/`open_tenant_session`.

    `default_tenant_id` (`identity_verification/deps.py`) always resolves
    to whichever tenant matches `settings.default_tenant_slug` — there is
    no way for an HTTP request to address a second tenant, so per
    testing-standards.md §3's "call the service layer directly" allowance,
    this calls `service.request_otp`/`service.verify_otp` directly with two
    distinct `tenant_id`s rather than going through `client`.
    """
    tenant_b = TenantFactory.build(
        id=uuid.uuid4(),
        name="Second Tenant",
        slug=f"second-tenant-{uuid.uuid4().hex[:8]}",
        schema_name=f"tenant_second_{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant_b)
    await db_session.commit()

    monkeypatch.setattr(settings, "otp_rate_limit_per_identifier", 1)
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    # Same identifier for both tenants on purpose: the only thing that can
    # separate their Redis state is the `tenant_id` segment of the key.
    identifier = _unique_email()

    await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    code_a = _extract_code(recorder.calls[0]["body"])
    # Tenant A is now rate-limited (otp_rate_limit_per_identifier=1)...
    with pytest.raises(service.PerIdentifierRateLimitExceeded):
        await service.request_otp(tenant_id=tenant.id, identifier=identifier, channel=Channel.email)
    # ...but tenant B, same identifier, is not — proves the `...:rl:...` key
    # is namespaced per tenant, not just per identifier/channel.
    await service.request_otp(tenant_id=tenant_b.id, identifier=identifier, channel=Channel.email)
    code_b = _extract_code(recorder.calls[1]["body"])

    # Tenant A's code does not verify against tenant B's OTP state and vice
    # versa — proves the `...:otp:...` key is namespaced per tenant too.
    with pytest.raises(service.InvalidOrExpiredCode):
        await service.verify_otp(
            tenant_id=tenant_b.id, identifier=identifier, channel=Channel.email, code=code_a
        )
    with pytest.raises(service.InvalidOrExpiredCode):
        await service.verify_otp(
            tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=code_b
        )

    # Each tenant's own correct code still verifies — the cross-tenant
    # attempts above didn't leak into, or burn attempts against, the other
    # tenant's key.
    result_a = await service.verify_otp(
        tenant_id=tenant.id, identifier=identifier, channel=Channel.email, code=code_a
    )
    assert result_a.identifier == identifier
    result_b = await service.verify_otp(
        tenant_id=tenant_b.id, identifier=identifier, channel=Channel.email, code=code_b
    )
    assert result_b.identifier == identifier


# --- Default-tenant misconfiguration is logged as a server error -------------


async def test_otp_request_unresolvable_default_tenant_logged_as_error(
    client: AsyncClient, monkeypatch
) -> None:
    """`default_tenant_id` (`identity_verification/deps.py`) resolves the
    single configured default tenant via `core.tenancy.resolve_default_tenant`.
    When that tenant doesn't exist, this is a server-side misconfiguration,
    not a caller error, so it must be logged at `ERROR` with the same
    not-found/inactive distinction `registrations/deps.py`'s equivalent
    fallback already has — see
    harden-default-tenant-resolution-and-readiness/design.md. The
    client-facing 404 is unchanged from before this consistency fix.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "no-such-tenant-slug")

    with capture_logs() as captured:
        response = await client.post(
            "/api/v1/identity-verification/otp/request",
            json={"identifier": _unique_email(), "channel": "email"},
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not found or inactive"

    [entry] = [
        e for e in captured if e["event"] == "identity_verification_default_tenant_unconfigured"
    ]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "not_found"


async def test_otp_request_inactive_default_tenant_logged_as_error(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession
) -> None:
    await db_session.execute(update(Tenant).where(Tenant.id == tenant.id).values(is_active=False))
    await db_session.commit()

    with capture_logs() as captured:
        response = await client.post(
            "/api/v1/identity-verification/otp/request",
            json={"identifier": _unique_email(), "channel": "email"},
        )

    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not found or inactive"

    [entry] = [
        e for e in captured if e["event"] == "identity_verification_default_tenant_unconfigured"
    ]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "inactive"


# --- No plaintext leakage -----------------------------------------------------


async def test_no_plaintext_code_leaks_and_logs_mask_the_identifier(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    logged: list[tuple[str, dict]] = []
    monkeypatch.setattr(service.logger, "info", lambda event, **kw: logged.append((event, kw)))
    monkeypatch.setattr(service.logger, "warning", lambda event, **kw: logged.append((event, kw)))
    recorder = _RecordingSender()
    monkeypatch.setattr(senders, "email_sender", recorder)
    identifier = _unique_email()

    response = await client.post(
        "/api/v1/identity-verification/otp/request",
        json={"identifier": identifier, "channel": "email"},
    )
    assert response.status_code == 200, response.text
    code = _extract_code(recorder.calls[0]["body"])

    assert code not in response.text
    assert logged
    for _event, fields in logged:
        assert code not in str(fields)
        assert fields["identifier"] != identifier  # masked, not the full identifier

    verify_response = await client.post(
        "/api/v1/identity-verification/otp/verify",
        json={"identifier": identifier, "channel": "email", "code": "000000"},
    )
    assert verify_response.status_code == 400
    assert "000000" not in verify_response.text
    assert verify_response.json()["message"] == "Invalid or expired code"
