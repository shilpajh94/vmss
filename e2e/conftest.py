"""Browser end-to-end suite for the portal's critical journeys
(VMSS_API openspec/changes/full-stack-qa-and-load-testing, spec "Browser
end-to-end suite for critical portal journeys").

Runs against Vite on :5173, which proxies /api to the local DDEV API, using
the shared QA fixtures and the per-role tokens the API repo mints:

    # in VMSS_API
    ddev exec uv run python scripts/qa_regression/seed_qa_fixtures.py
    ddev exec uv run python scripts/qa_regression/mint_tokens.py
    # in VMMS_WEB (needs `npm run dev` running)
    npm run e2e

Staff accounts can't password-login (SSO only), so each journey signs in by
putting a minted token in `sessionStorage`, as the SSO callback does. Any
uncaught page error or 5xx API response fails the journey, and its
screenshot and trace are kept under `e2e-results/`.
"""

import datetime
import json
import os
import re
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import APIRequestContext, BrowserContext, Locator, Page, Playwright

TOKENS_PATH = Path(os.environ.get("E2E_TOKENS", "/tokens/tokens.json"))
MAILPIT_URL = os.environ.get("E2E_MAILPIT_URL", "https://vmss-new-api.ddev.site:8026")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "admin12345")

# A valid 1x1 JPEG, for the ID-proof upload the invitation API requires.
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c"
    "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27"
    "393d38323c2e333432ffc0000b080001000101011100ffc4001f0000010501010101010100000000"
    "000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300"
    "041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a"
    "25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475"
    "767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9ba"
    "c2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda"
    "0008010100003f00fbd3ffd9"
)


def run_tag() -> str:
    return uuid.uuid4().hex[:6].upper()


def select_matching(select: Locator, pattern: str) -> None:
    """`select_option` by a case-insensitive pattern over the option texts
    (Python Playwright's `label=` only takes an exact string)."""
    texts = select.locator("option").all_inner_texts()
    match = next((t for t in texts if re.search(pattern, t, re.I)), None)
    assert match, f"no option matching {pattern!r} in {texts}"
    select.select_option(label=match)


def wait_for(read: Callable[[], Any], expected: Any, timeout: float = 10.0) -> None:
    """Polls `read()` until it returns `expected` (Python Playwright has no
    `expect.poll`) — for state the UI changes through the API."""
    deadline = time.monotonic() + timeout
    value = read()
    while value != expected and time.monotonic() < deadline:
        time.sleep(0.25)
        value = read()
    assert value == expected, f"expected {expected!r}, last saw {value!r}"


@pytest.fixture(scope="session")
def tokens() -> dict[str, Any]:
    if not TOKENS_PATH.exists():
        pytest.exit(
            f"{TOKENS_PATH} not found — run VMSS_API's scripts/qa_regression/mint_tokens.py "
            "and mount its var/qa directory at /tokens (npm run e2e does this).",
            returncode=2,
        )
    return json.loads(TOKENS_PATH.read_text())


class Api:
    """Thin client over the same origin the portal uses, for arranging
    state a journey starts from and for cleaning up after it."""

    def __init__(self, request: APIRequestContext, tokens: dict[str, Any]) -> None:
        self.request = request
        self.tokens = tokens
        self.branches: dict[str, str] = tokens["branches"]
        self.categories: dict[str, str] = tokens["categories"]
        self._form: list[dict[str, Any]] | None = None
        self._buildings: dict[str, str] | None = None

    def headers(self, role: str | None, branch: str | None = "MAIN") -> dict[str, str]:
        headers: dict[str, str] = {}
        if role is not None:
            headers["Authorization"] = f"Bearer {self.tokens['users'][role]['token']}"
        if branch is not None:
            headers["X-Branch-ID"] = self.branches[branch]
        return headers

    def call(
        self,
        method: str,
        path: str,
        role: str | None = "admin",
        *,
        expect: int | None = None,
        branch: str | None = "MAIN",
        **kwargs: Any,
    ) -> Any:
        if "json" in kwargs:  # Playwright serialises a dict `data` as JSON
            kwargs["data"] = kwargs.pop("json")
        response = self.request.fetch(
            path, method=method, headers=self.headers(role, branch), **kwargs
        )
        if expect is not None:
            assert response.status == expect, (
                f"{method} {path}: {response.status} {response.text()}"
            )
        try:
            return response.json().get("data")
        except ValueError:
            return None

    def user_id(self, role: str) -> str:
        return self.tokens["users"][role]["userId"]

    def building(self, branch: str = "MAIN") -> str:
        if self._buildings is None:
            rows = self.call("GET", "/api/v1/buildings", expect=200, branch=None) or []
            self._buildings = {}
            for code, branch_id in self.branches.items():
                match = [b["id"] for b in rows if b["branchId"] == branch_id]
                if match:
                    self._buildings[code] = match[0]
        return self._buildings[branch]

    def create_invitation(self, name: str, role: str = "host", category: str = "QA_MULTI") -> dict:
        if self._form is None:
            self._form = self.call("GET", "/api/v1/form-builder/effective", expect=200)
        fields = {f["key"]: f for step in self._form for f in step.get("fields", [])}
        consents = [
            {"fieldId": fields[k]["id"], "accepted": True}
            for k in ("terms_accepted", "data_processing_accepted", "safety_guidelines_accepted")
            if k in fields and fields[k].get("isActive", True)
        ]
        payload = {
            "registrationType": "individual",
            "branchId": self.branches["MAIN"],
            "buildingId": self.building(),
            "visitorCategoryId": self.categories[category],
            "primaryContact": {
                "fullName": name,
                "email": f"{re.sub(r'[^a-z0-9]+', '.', name.lower()).strip('.')}@example.com",
                "preferredContactMethod": "email",
            },
            "visitDetails": {
                "purposeOfVisit": "QA e2e",
                "preferredVisitDate": str(datetime.date.today()),
                "preferredVisitTime": "10:00:00",
                "expectedDuration": "< 1 hour",
            },
            "consents": consents,
        }
        return self.call(
            "POST",
            "/api/v1/invitations",
            role,
            expect=201,
            multipart={
                "payload": json.dumps(payload),
                "primary_contact_id_proof_file": {
                    "name": "id.jpg",
                    "mimeType": "image/jpeg",
                    "buffer": JPEG,
                },
            },
        )

    def invitation(self, invitation_id: str) -> dict:
        return self.call("GET", f"/api/v1/invitations/{invitation_id}", expect=200, branch=None)

    def check_in(self, tracking_id: str) -> None:
        """Check-in has no portal UI — kiosks and the gate app do it via
        the public endpoint, so the journey does the same."""
        self.call(
            "PATCH", f"/api/v2/invitations/{tracking_id}/check-in", None, expect=200, branch=None
        )

    def latest_otp(self, email: str) -> str:
        response = self.request.get(
            f"{MAILPIT_URL}/api/v1/search",
            params={"query": f'to:"{email}" subject:"verification code"', "limit": 1},
        )
        messages = response.json().get("messages") or []
        assert messages, f"no OTP email for {email} in Mailpit"
        body = self.request.get(f"{MAILPIT_URL}/api/v1/message/{messages[0]['ID']}").json()
        match = re.search(r"Verification code:\s*(\d{4,8})", body["Text"])
        assert match, "OTP email has no code"
        return match.group(1)


@pytest.fixture(scope="session")
def api(playwright: Playwright, base_url: str, tokens: dict[str, Any]) -> Iterator[Api]:
    request = playwright.request.new_context(base_url=base_url, ignore_https_errors=True)
    yield Api(request, tokens)
    request.dispose()


def _watch(context: BrowserContext, errors: list[str]) -> None:
    def attach(page: Page) -> None:
        page.on("pageerror", lambda exc: errors.append(f"page error: {exc}"))
        page.on(
            "response",
            lambda response: (
                errors.append(f"HTTP {response.status} {response.request.method} {response.url}")
                if response.status >= 500
                else None
            ),
        )

    for page in context.pages:
        attach(page)
    context.on("page", attach)


@pytest.fixture
def as_role(
    request: pytest.FixtureRequest,
    new_context: Callable[..., BrowserContext],
    tokens: dict[str, Any],
) -> Callable[[str], Page]:
    """`as_role("reception")` -> a page in its own browser context, signed
    in as that QA user (or anonymous for "anonymous")."""
    errors: list[str] = request.node.__dict__.setdefault("_browser_errors", [])

    def _open(role: str) -> Page:
        context = new_context(viewport={"width": 1440, "height": 900})
        _watch(context, errors)
        if role != "anonymous":
            token = tokens["users"][role]["token"]
            # Runs in every frame; sandboxed ones (e.g. Firebase's) deny
            # sessionStorage, which would otherwise surface as a page error.
            context.add_init_script(
                f"try {{ sessionStorage.setItem('token', {json.dumps(token)}) }} catch {{}}"
            )
        return context.new_page()

    return _open


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Fails the journey (in the call phase, so pytest-playwright keeps its
    screenshot and trace) when the page threw or the API returned a 5xx,
    even if every explicit assertion passed."""
    outcome = yield
    errors = item.__dict__.get("_browser_errors") or []
    if errors and outcome.excinfo is None:
        outcome.force_exception(AssertionError("browser errors:\n  " + "\n  ".join(errors)))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        marker = item.get_closest_marker("known_issue")
        if marker:
            item.add_marker(pytest.mark.xfail(reason=f"known issue {marker.args[0]}", strict=True))
