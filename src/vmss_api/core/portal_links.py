"""Absolute web-app URLs that notification emails link to
(add-portal-links-to-emails design.md Decision 2). The paths here are a
contract with the VMMS_WEB router — change them only together with it.

Every builder returns `None` when no portal base URL is configured, and the
email then renders without its call-to-action button.
"""

from urllib.parse import urlsplit

from vmss_api.core.config import settings
from vmss_api.core.logging import logger

VISITOR_TRACK_PATH = "/visitor/track"
VISITOR_REQUEST_PATH = "/visitor/request"
STAFF_LOGIN_PATH = "/staff/login"

_warned_base_url_unset = False


def base_url() -> str | None:
    """The origin (scheme + host) of `STAFF_PORTAL_URL`, or `None` — warned
    once per process, not per email — when it's unset or isn't an
    `http(s)://` URL. The latter covers an environment whose pipeline left
    the `__STAFF_PORTAL_URL__` token unreplaced, which would otherwise
    produce broken links. Only the origin is kept because deployments set
    this to a page (e.g. `https://host/staff/login`) from when it fed a
    single "open the portal" link.
    """
    global _warned_base_url_unset
    parts = urlsplit((settings.staff_portal_url or "").strip())
    if parts.scheme in ("https", "http") and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    if not _warned_base_url_unset:
        _warned_base_url_unset = True
        logger.warning(
            "portal_base_url_unset",
            setting="STAFF_PORTAL_URL",
            effect="notification emails are sent without portal links",
        )
    return None


def _url(path: str) -> str | None:
    base = base_url()
    return f"{base}{path}" if base else None


def visitor_track_url() -> str | None:
    return _url(VISITOR_TRACK_PATH)


def visitor_request_url() -> str | None:
    return _url(VISITOR_REQUEST_PATH)


def staff_login_url() -> str | None:
    return _url(STAFF_LOGIN_PATH)
