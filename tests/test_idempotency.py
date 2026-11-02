"""api-compliance-hardening "Idempotency Keys Are Scoped to One Endpoint,
Caller, and Request" — the `core/idempotency.py` guard, exercised directly
so concurrency can be staged deterministically."""

import json
import uuid
from types import SimpleNamespace

from fastapi import Request
from fastapi.responses import JSONResponse

from vmss_api.core.idempotency import Idempotency

_TENANT = uuid.uuid4()


def _request(method: str, route: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": b"",
            "headers": [],
            "route": SimpleNamespace(path=route),
        }
    )


def _check_in() -> Request:
    return _request("PATCH", "/invitations/code/check-in", "/api/v2/invitations/code/check-in")


def _check_out() -> Request:
    return _request("PATCH", "/invitations/code/check-out", "/api/v2/invitations/code/check-out")


async def _begin(
    guard: Idempotency,
    key: str,
    *,
    caller: str = "dev-1",
    body: str = "{}",
    namespace: str = "invitations",
) -> JSONResponse | None:
    return await guard.begin(_TENANT, namespace, key, caller=caller, body=body)


async def _complete(guard: Idempotency, body: dict) -> None:
    await guard.store(JSONResponse(content=body))
    await guard.release()


async def test_genuine_retry_replays_the_original_response() -> None:
    key = uuid.uuid4().hex
    first = Idempotency(_check_in())
    assert await _begin(first, key, body='{"code":"1"}') is None
    await _complete(first, {"data": "checked in"})

    retry = Idempotency(_check_in())
    cached = await _begin(retry, key, body='{"code":"1"}')
    assert cached is not None
    assert json.loads(bytes(cached.body)) == {"data": "checked in"}


async def test_same_key_on_another_endpoint_does_not_replay() -> None:
    key = uuid.uuid4().hex
    check_in = Idempotency(_check_in())
    await _begin(check_in, key, body='{"code":"1"}')
    await _complete(check_in, {"data": "checked in"})

    check_out = Idempotency(_check_out())
    assert await _begin(check_out, key, body='{"code":"1"}') is None
    await check_out.release()


async def test_same_key_from_another_caller_does_not_replay() -> None:
    """The OTP case: verify for identifier B must never get A's proof token."""
    key = uuid.uuid4().hex
    route = "/identity-verification/otp/verify"
    otp = _request("POST", route, f"/api/v1{route}")
    first = Idempotency(otp)
    await _begin(first, key, caller="a@example.com", namespace="identity-verification")
    await _complete(first, {"data": {"proofToken": "token-for-a"}})

    second = Idempotency(otp)
    assert (
        await _begin(second, key, caller="b@example.com", namespace="identity-verification") is None
    )
    await second.release()


async def test_same_key_with_a_different_body_is_rejected() -> None:
    key = uuid.uuid4().hex
    first = Idempotency(_check_in())
    await _begin(first, key, body='{"code":"1"}')
    await _complete(first, {"data": "checked in"})

    reused = Idempotency(_check_in())
    response = await _begin(reused, key, body='{"code":"2"}')
    assert response is not None
    assert response.status_code == 422


async def test_concurrent_duplicate_is_rejected_while_the_first_is_in_flight() -> None:
    key = uuid.uuid4().hex
    first = Idempotency(_check_in())
    assert await _begin(first, key, body="{}") is None

    duplicate = Idempotency(_check_in())
    response = await _begin(duplicate, key, body="{}")
    assert response is not None
    assert response.status_code == 409

    await _complete(first, {"data": "done"})
    replay = Idempotency(_check_in())
    assert (await _begin(replay, key, body="{}")) is not None


async def test_failed_attempt_releases_its_lock_so_a_retry_runs() -> None:
    key = uuid.uuid4().hex
    failed = Idempotency(_check_in())
    await _begin(failed, key, body="{}")
    await failed.release()  # the dependency's cleanup, after an error response

    retry = Idempotency(_check_in())
    assert await _begin(retry, key, body="{}") is None
    await retry.release()


async def test_no_key_means_no_dedup() -> None:
    guard = Idempotency(_check_in())
    assert await guard.begin(_TENANT, "invitations", None, caller="dev-1") is None
    await guard.store(JSONResponse(content={}))  # no-op
    await guard.release()
