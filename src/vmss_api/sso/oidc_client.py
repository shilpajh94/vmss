"""All outbound HTTP to a tenant's configured OIDC identity provider:
discovery-document fetch, the authorization-code-for-tokens exchange, a
client-credentials probe for the admin "test connection" check, and
ID-token verification against the IdP's published JWKS.

Every network call here goes through a plain `httpx.AsyncClient()`, created
and closed within the call — `sso/tests.py` intercepts it with `respx`
(which patches httpx's transport layer globally, so no dependency-injection
scaffolding is needed for a real IdP to never be reached in tests).
"""

import ipaddress
import socket
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode, urlsplit

import anyio
import httpx
import jwt
from jwt import PyJWKClient

_HTTP_TIMEOUT_SECONDS = 10.0


class UnsafeDiscoveryUrlError(RuntimeError):
    """`discovery_url` uses a non-`https` scheme, or resolves to a
    private/loopback/link-local/multicast/reserved address — the standard
    SSRF guard for a server-side request built from admin-supplied input
    (`PUT /auth/sso/config`, `POST /auth/sso/config/test`). Without this, an
    authenticated `sso-config:manage` caller could point the server at an
    internal service or a cloud metadata endpoint. See design.md's "SSRF
    guard" decision.
    """


def _resolve_host_ips(hostname: str) -> list[str]:
    """Isolated so tests can stub DNS resolution instead of depending on
    real network behavior in CI — see `sso/tests.py`'s
    `_stub_dns_resolution` fixture, which defaults every test to a safe
    public IP so the many tests using fake `*.example.com` discovery hosts
    (which don't really resolve) keep working, while the SSRF-specific
    tests override it to a private/loopback address to prove rejection.
    """
    return [str(info[4][0]) for info in socket.getaddrinfo(hostname, None)]


async def _assert_safe_outbound_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeDiscoveryUrlError("Only https:// URLs are allowed")
    if not parsed.hostname:
        raise UnsafeDiscoveryUrlError("URL has no host")

    try:
        resolved_ips = await anyio.to_thread.run_sync(_resolve_host_ips, parsed.hostname)
    except socket.gaierror as exc:
        raise UnsafeDiscoveryUrlError(f"Could not resolve host: {exc}") from exc

    for raw_ip in resolved_ips:
        address = ipaddress.ip_address(raw_ip)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
        ):
            raise UnsafeDiscoveryUrlError(
                "URL resolves to a private, loopback, link-local, or reserved address"
            )


class OidcDiscoveryError(RuntimeError):
    """The discovery document could not be fetched or is missing a
    required field."""


class OidcConfigTestError(RuntimeError):
    """The "test connection" check failed — caller-safe message, no
    upstream response body leaked."""


class OidcTokenExchangeError(RuntimeError):
    """The authorization-code-for-tokens exchange failed."""


class InvalidIdTokenError(RuntimeError):
    """The ID token failed signature, issuer, audience, expiry, or nonce
    verification."""


@dataclass(frozen=True)
class DiscoveryDocument:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


async def fetch_discovery_document(discovery_url: str) -> DiscoveryDocument:
    await _assert_safe_outbound_url(discovery_url)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(discovery_url, timeout=_HTTP_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OidcDiscoveryError(f"Could not fetch the OIDC discovery document: {exc}") from exc
    try:
        return DiscoveryDocument(
            issuer=data["issuer"],
            authorization_endpoint=data["authorization_endpoint"],
            token_endpoint=data["token_endpoint"],
            jwks_uri=data["jwks_uri"],
        )
    except KeyError as exc:
        raise OidcDiscoveryError(f"Discovery document is missing required field {exc}") from exc


def build_authorization_url(
    discovery: DiscoveryDocument,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    scope: str = "openid profile email",
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "nonce": nonce,
    }
    return f"{discovery.authorization_endpoint}?{urlencode(params)}"


async def exchange_code_for_tokens(
    discovery: DiscoveryDocument,
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                discovery.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OidcTokenExchangeError(f"Token exchange with the IdP failed: {exc}") from exc
        return response.json()


async def test_client_credentials(
    discovery_url: str, *, client_id: str, client_secret: str
) -> None:
    """Validates a candidate discovery URL and client credentials without
    completing a real user login — design.md's "Provider Connection Can Be
    Tested Before Saving" decision. Attempts a `client_credentials` grant:
    an app registration that only supports delegated (user sign-in) flows
    may still reject the requested scope, but the IdP only returns
    `invalid_client` when the client ID/secret pair itself is wrong, which
    is the one thing this check needs to catch before an Admin saves a
    typo'd secret and locks staff out.
    """
    discovery = await fetch_discovery_document(discovery_url)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                discovery.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "openid",
                },
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise OidcConfigTestError(f"Could not reach the IdP's token endpoint: {exc}") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    if body.get("error") == "invalid_client":
        raise OidcConfigTestError("The IdP rejected the client ID or client secret")


@lru_cache(maxsize=64)
def _jwk_client(jwks_uri: str) -> PyJWKClient:
    """Cached per `jwks_uri` so repeated logins against the same tenant
    reuse `PyJWKClient`'s own key cache instead of re-fetching the IdP's
    JWKS on every callback — see design.md's Risk on key-rotation timing:
    a cache miss on an unknown `kid` still triggers a fresh fetch before
    failing, this cache just avoids rebuilding the client object itself.
    """
    return PyJWKClient(jwks_uri)


def verify_id_token(
    id_token: str, *, jwks_uri: str, issuer: str, audience: str, nonce: str
) -> dict[str, Any]:
    """Verifies signature (against the IdP's published JWKS), issuer,
    audience, and expiry via `PyJWT`, then checks `nonce` separately (PyJWT
    has no built-in nonce check) — see design.md's "Verifying
    externally-issued tokens" decision.
    """
    try:
        signing_key = _jwk_client(jwks_uri).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token, signing_key.key, algorithms=["RS256"], audience=audience, issuer=issuer
        )
    except jwt.PyJWTError as exc:
        raise InvalidIdTokenError(str(exc)) from exc
    if claims.get("nonce") != nonce:
        raise InvalidIdTokenError("ID token nonce does not match the login attempt")
    return claims
