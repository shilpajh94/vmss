"""Deprecate-then-enforce for unauthenticated access that leaks staff PII or
changes visit state (public-endpoint-hardening spec; audit-and-harden-api-
and-web design.md D4).

`PUBLIC_ENDPOINT_HARDENING` is off by default, so the web, Flutter and
kiosk clients keep working. While it's off, a request served without the
credential strict mode would require is answered as before, but flagged
with `Deprecation`/`Link` headers so client teams can see what to migrate.
"""

from fastapi.responses import JSONResponse

from vmss_api.core.config import settings
from vmss_api.core.responses import mark_deprecated

_DOCS = "docs/features"


def strict_public_access() -> bool:
    return settings.public_endpoint_hardening


def flag_legacy_access(response: JSONResponse, *, feature_doc: str) -> JSONResponse:
    """Marks a response served under the legacy (pre-hardening) contract.
    `feature_doc` names the `docs/features/*.md` page describing what
    strict mode will require."""
    mark_deprecated(response)
    target = f"{_DOCS}/{feature_doc}#public-endpoint-hardening"
    response.headers["Link"] = f'<{target}>; rel="deprecation"'
    return response
