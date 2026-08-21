import asyncio
import re
import time
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
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
