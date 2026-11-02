"""environment-configuration "Placeholder Secrets Are Refused Outside Local
and Testing" and rate-limiting "Rate Limits Key on the Real Client Address
Behind a Trusted Proxy" (audit-and-harden-api-and-web)."""

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from vmss_api.core.config import InsecureConfigurationError, Settings
from vmss_api.main import create_app

_STRONG_SECRET = "s" * 48


@pytest.mark.parametrize(
    "secret",
    ["change-me-in-env", "__JWT_SECRET_KEY__", "a_PLACEHOLDER_value_padded_to_length", "x7Kq-tiny"],
)
def test_enforced_check_refuses_a_placeholder_jwt_secret(secret: str) -> None:
    with pytest.raises(InsecureConfigurationError) as excinfo:
        Settings(
            _env_file=None, APP_ENV="production", ENFORCE_SECRET_CHECK=True, jwt_secret_key=secret
        )
    message = str(excinfo.value)
    assert "JWT_SECRET_KEY" in message
    assert secret not in message


def test_unenforced_check_only_warns() -> None:
    with pytest.warns(RuntimeWarning, match="JWT_SECRET_KEY") as record:
        assert Settings(_env_file=None, APP_ENV="production", jwt_secret_key="x7Kq-tiny")
    assert all("x7Kq-tiny" not in str(warning.message) for warning in record)


def test_production_accepts_a_real_secret() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        ENFORCE_SECRET_CHECK=True,
        jwt_secret_key=_STRONG_SECRET,
    )
    assert settings.enforce_secret_check


@pytest.mark.parametrize("environment", ["local", "test", "testing"])
def test_local_and_test_environments_keep_the_placeholder(environment: str) -> None:
    assert Settings(_env_file=None, APP_ENV=environment, jwt_secret_key="change-me-in-env")


async def _client_host_seen(peer: str, forwarded_for: str) -> str:
    app = create_app()

    @app.get("/__client-host")
    async def _client_host(request: Request) -> dict[str, str]:
        assert request.client is not None
        return {"host": request.client.host}

    transport = ASGITransport(app=app, client=(peer, 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/__client-host", headers={"X-Forwarded-For": forwarded_for})
    return response.json()["host"]


async def test_trusted_proxy_forwards_the_real_client_address() -> None:
    # The default FORWARDED_ALLOW_IPS trusts a same-host proxy.
    assert await _client_host_seen("127.0.0.1", "203.0.113.9") == "203.0.113.9"


async def test_untrusted_peer_cannot_spoof_its_address() -> None:
    assert await _client_host_seen("198.51.100.7", "203.0.113.9") == "198.51.100.7"
