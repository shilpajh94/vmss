"""API regression runner — drives every feature router's main endpoints over
real HTTP against the running local stack, as each QA role, and fails on any
5xx, unexpected status, or non-envelope JSON body
(openspec/changes/full-stack-qa-and-load-testing, spec "API regression
runner covers every router").

Unlike pytest (whose `client` fixture routes `get_db` and `get_tenant_db` to
one shared session), this goes through the real middleware, sessions, Redis,
Celery dispatch and rate limiter the deployed app uses.

Prerequisites (local default tenant only):
    ddev exec uv run python scripts/qa_regression/seed_qa_fixtures.py
    ddev exec uv run python scripts/qa_regression/mint_tokens.py

Usage:
    ddev exec uv run python scripts/qa_regression/run.py \
        [--base-url http://localhost:8000] [--only invitations,approvals] \
        [--skip-rate-limit]

Writes `var/qa/api-results.json` and prints a summary table. Exit code 1 on
any failure or uncovered router tag.

Every created invitation's primary contact is named `QA Visitor ...` so
`reset_qa_data.py` can remove it; other created entities are deleted again
through their own DELETE endpoints, which exercises those too.
"""

import argparse
import io
import json
import sys
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TOKENS_PATH = ROOT / "var" / "qa" / "tokens.json"
RESULTS_PATH = ROOT / "var" / "qa" / "api-results.json"
RUN_STAMP = ROOT / "var" / "qa" / ".last-full-run"

# Tags with no business endpoints worth a role matrix still need one happy
# path; this is checked against the live /openapi.json, not this list.
Expect = int | Iterable[int]

# Findings already triaged as non-blockers in the QA report
# (docs/qa/2026-10-full-stack-qa.md). A matching call that misbehaves is
# reported as KNOWN with its finding id instead of failing the run; once the
# follow-up lands and the call passes, it shows as STALE so the entry gets
# removed. Keyed by (tag, case name).
KNOWN_ISSUES: dict[tuple[str, str], str] = {
    ("invitations", "list pageSize over max rejected"): "F2",
    ("invitations", "list bad sortBy rejected"): "F2",
}


@dataclass
class Result:
    tag: str
    name: str
    method: str
    path: str
    role: str
    expected: list[int]
    status: int | None
    ok: bool
    envelope_ok: bool | None
    latency_ms: float
    request_id: str | None
    detail: str = ""
    known_issue: str | None = None


@dataclass
class Runner:
    base_url: str
    tokens: dict[str, Any]
    results: list[Result] = field(default_factory=list)
    run_tag: str = field(default_factory=lambda: uuid.uuid4().hex[:6].upper())

    def __post_init__(self) -> None:
        self.http = httpx.Client(base_url=self.base_url, timeout=60.0, follow_redirects=False)
        self.branches: dict[str, str] = self.tokens["branches"]
        self.categories: dict[str, str] = self.tokens["categories"]
        self.users: dict[str, dict[str, str]] = self.tokens["users"]

    # --- plumbing ---------------------------------------------------------

    def _auth_header(self, role: str | None) -> dict[str, str]:
        if role is None or role == "anonymous":
            return {}
        if role == "superadmin":
            token = self.tokens["superadmin"]["token"]
        elif role == "visitor":
            token = self.tokens["visitor"]["token"]
        elif role == "garbage":
            token = "not-a-jwt"
        else:
            token = self.users[role]["token"]
        return {"Authorization": f"Bearer {token}"}

    def call(
        self,
        tag: str,
        name: str,
        method: str,
        path: str,
        role: str | None,
        expect: Expect,
        *,
        branch: str | None = "MAIN",
        envelope: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response | None:
        expected = [expect] if isinstance(expect, int) else list(expect)
        all_headers = self._auth_header(role)
        if branch is not None:
            all_headers["X-Branch-ID"] = self.branches.get(branch, branch)
        all_headers.update(headers or {})
        started = time.perf_counter()
        try:
            response = self.http.request(method, path, headers=all_headers, **kwargs)
        except httpx.HTTPError as exc:
            self.results.append(
                Result(
                    tag,
                    name,
                    method,
                    path,
                    role or "anonymous",
                    expected,
                    None,
                    False,
                    None,
                    (time.perf_counter() - started) * 1000,
                    None,
                    f"transport error: {exc!r}",
                )
            )
            return None
        latency_ms = (time.perf_counter() - started) * 1000
        envelope_ok = self._check_envelope(response) if envelope else None
        ok = response.status_code in expected and envelope_ok is not False
        detail = ""
        if not ok:
            detail = response.text[:400]
        known = KNOWN_ISSUES.get((tag, name))
        self.results.append(
            Result(
                tag,
                name,
                method,
                path,
                role or "anonymous",
                expected,
                response.status_code,
                ok,
                envelope_ok,
                round(latency_ms, 1),
                response.headers.get("x-request-id"),
                detail,
                known,
            )
        )
        return response

    @staticmethod
    def _check_envelope(response: httpx.Response) -> bool | None:
        if response.status_code == 204 or not response.content:
            return None
        if "application/json" not in response.headers.get("content-type", ""):
            return False
        try:
            body = response.json()
        except ValueError:
            return False
        if not isinstance(body, dict) or not isinstance(body.get("success"), bool):
            return False
        if not isinstance(body.get("message"), str):
            return False
        if body["success"] and "data" not in body:
            return False
        return body["success"] == (response.status_code < 400)

    @staticmethod
    def data(response: httpx.Response | None) -> Any:
        if response is None or response.status_code >= 400:
            return None
        try:
            return response.json().get("data")
        except ValueError:
            return None

    def id_of(self, response: httpx.Response | None) -> str | None:
        payload = self.data(response)
        return payload.get("id") if isinstance(payload, dict) else None

    # --- shared builders --------------------------------------------------

    @staticmethod
    def jpeg() -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), color="white").save(buffer, format="JPEG")
        return buffer.getvalue()

    def effective_form(self, branch: str = "MAIN") -> list[dict[str, Any]]:
        response = self.http.get(
            "/api/v1/form-builder/effective",
            headers={**self._auth_header("admin"), "X-Branch-ID": self.branches[branch]},
        )
        response.raise_for_status()
        return response.json()["data"]

    def invitation_payload(
        self, label: str, *, category: str, branch: str = "MAIN", building_id: str | None = None
    ) -> dict[str, Any]:
        fields = {f["key"]: f for s in self._form for f in s.get("fields", [])}
        consent_keys = [
            k
            for k in ("terms_accepted", "data_processing_accepted", "safety_guidelines_accepted")
            if k in fields and fields[k].get("isActive", True)
        ]
        suffix = f"{label}{self.run_tag}"
        return {
            "registrationType": "individual",
            "branchId": self.branches[branch],
            "buildingId": building_id or self.buildings[branch],
            "visitorCategoryId": self.categories[category],
            "primaryContact": {
                "fullName": f"QA Visitor {suffix}",
                "email": f"qa.visitor.{suffix.lower()}@example.com",
                "preferredContactMethod": "email",
            },
            "visitDetails": {
                "purposeOfVisit": f"QA regression {label}",
                "preferredVisitDate": str(date.today()),
                "preferredVisitTime": "10:00:00",
                "expectedDuration": "< 1 hour",
            },
            "consents": [{"fieldId": fields[k]["id"], "accepted": True} for k in consent_keys],
        }

    def create_invitation(
        self,
        label: str,
        role: str,
        *,
        category: str = "QA_MULTI",
        expect: Expect = 201,
        branch: str = "MAIN",
        idempotency_key: str | None = None,
        tag: str = "invitations",
    ) -> dict[str, Any] | None:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        response = self.call(
            tag,
            f"create invitation ({label})",
            "POST",
            "/api/v1/invitations",
            role,
            expect,
            branch=branch,
            headers=headers,
            data={
                "payload": json.dumps(
                    self.invitation_payload(label, category=category, branch=branch)
                )
            },
            files={"primary_contact_id_proof_file": ("id.jpg", self.jpeg(), "image/jpeg")},
        )
        return self.data(response)

    def invitation(self, invitation_id: str) -> dict[str, Any] | None:
        response = self.http.get(
            f"/api/v1/invitations/{invitation_id}", headers=self._auth_header("admin")
        )
        return response.json().get("data") if response.status_code == 200 else None

    def approve_fully(self, invitation_id: str, tag: str = "approvals") -> bool:
        """Walks QA_MULTI's reception -> host chain the way the portal does:
        reception approves step 1, delegates the host step, the delegate
        approves it."""
        for _ in range(4):
            inv = self.invitation(invitation_id)
            if inv is None:
                return False
            if inv["status"] != "submitted":
                return inv["status"] == "approved"
            step = inv["currentApprovalStep"]
            if step is None:
                return False
            base = f"/api/v1/invitations/{invitation_id}/approval-steps/{step['id']}"
            if step["stepOrder"] >= 2 and step.get("delegatedToUserId") is None:
                self.call(
                    tag,
                    "delegate host step",
                    "POST",
                    f"{base}/delegate",
                    "reception",
                    200,
                    json={"delegateUserId": self.users["approver"]["userId"]},
                )
                self.call(
                    tag,
                    "approve delegated host step",
                    "POST",
                    f"{base}/approve",
                    "approver",
                    200,
                    json={},
                )
            else:
                self.call(
                    tag,
                    f"approve step {step['stepOrder']}",
                    "POST",
                    f"{base}/approve",
                    "reception",
                    200,
                    json={},
                )
        inv = self.invitation(invitation_id)
        return inv is not None and inv["status"] == "approved"

    # --- scenarios --------------------------------------------------------

    def setup(self) -> None:
        self._form = self.effective_form()
        response = self.http.get("/api/v1/buildings", headers=self._auth_header("admin"))
        response.raise_for_status()
        self.buildings: dict[str, str] = {}
        for code, branch_id in self.branches.items():
            match = [b for b in response.json()["data"] if b["branchId"] == branch_id]
            if match:
                self.buildings[code] = match[0]["id"]

    def health(self) -> None:
        self.call("health", "liveness", "GET", "/health", None, 200, branch=None, envelope=False)
        self.call(
            "health", "readiness", "GET", "/health/ready", None, 200, branch=None, envelope=False
        )

    def auth(self) -> None:
        t = "auth"
        for role in ("admin", "reception", "security", "host", "approver", "norole", "branchb"):
            self.call(t, "me", "GET", "/api/v1/auth/me", role, 200, branch=None)
        self.call(t, "me without token", "GET", "/api/v1/auth/me", None, 401, branch=None)
        self.call(t, "me with garbage token", "GET", "/api/v1/auth/me", "garbage", 401, branch=None)
        self.call(
            t,
            "avatar upload",
            "POST",
            "/api/v1/auth/me/avatar",
            "host",
            200,
            branch=None,
            files={"file": ("me.jpg", self.jpeg(), "image/jpeg")},
        )
        self.call(
            t,
            "avatar disguised content rejected",
            "POST",
            "/api/v1/auth/me/avatar",
            "host",
            (400, 415, 422),
            branch=None,
            files={"file": ("me.jpg", b"MZ\x90\x00 not an image", "image/jpeg")},
        )
        self.call(t, "permissions", "GET", "/api/v1/auth/permissions", "admin", 200, branch=None)
        self.call(t, "roles list", "GET", "/api/v1/auth/roles", "admin", 200, branch=None)
        self.call(
            t, "roles list (branch-scoped reception)", "GET", "/api/v1/auth/roles", "reception", 200
        )
        self.call(
            t,
            "roles list denied (no role)",
            "GET",
            "/api/v1/auth/roles",
            "norole",
            403,
            branch=None,
        )
        self.call(
            t,
            "role name verify",
            "GET",
            "/api/v1/auth/roles/verify",
            "admin",
            200,
            branch=None,
            params={"name": f"QA Runner {self.run_tag}"},
        )
        role = self.call(
            t,
            "role create",
            "POST",
            "/api/v1/auth/roles",
            "admin",
            201,
            branch=None,
            json={"name": f"QA Runner {self.run_tag}", "permissionCodes": ["invitations:view"]},
        )
        role_id = self.id_of(role)
        if role_id:
            self.call(
                t, "role get", "GET", f"/api/v1/auth/roles/{role_id}", "admin", 200, branch=None
            )
            self.call(
                t,
                "role update",
                "PUT",
                f"/api/v1/auth/roles/{role_id}",
                "admin",
                200,
                branch=None,
                json={"description": "QA runner role"},
            )
            self.call(
                t,
                "role delete",
                "DELETE",
                f"/api/v1/auth/roles/{role_id}",
                "admin",
                (200, 204),
                branch=None,
            )
        self.call(
            t,
            "resync role permissions",
            "POST",
            "/api/v1/auth/roles/resync-permissions",
            "admin",
            200,
            branch=None,
        )
        self.call(
            t,
            "resync denied (reception)",
            "POST",
            "/api/v1/auth/roles/resync-permissions",
            "reception",
            403,
            branch=None,
        )

        created = self.call(
            t,
            "user create (fixed QA email)",
            "POST",
            "/api/v1/auth/users",
            "admin",
            (201, 409),
            branch=None,
            json={
                "email": "qa.created@example.com",
                "password": "qa-created-12345",
                "fullName": "QA Created",
            },
        )
        user_id = self.id_of(created) or self._user_id_by_email("qa.created@example.com")
        if user_id:
            roles = (
                self.data(
                    self.http.get(
                        "/api/v1/auth/roles",
                        params={"pageSize": 100},
                        headers=self._auth_header("admin"),
                    )
                )
                or []
            )
            host_role = next((r["id"] for r in roles if r["name"] == "host"), None)
            assignment = self.call(
                t,
                "branch-role assign",
                "POST",
                f"/api/v1/auth/users/{user_id}/branch-roles",
                "admin",
                (201, 409),
                branch=None,
                json={"roleId": host_role, "branchId": self.branches.get("QAFB")},
            )
            assignment_id = self.id_of(assignment)
            if assignment_id:
                self.call(
                    t,
                    "branch-role revoke",
                    "DELETE",
                    f"/api/v1/auth/users/{user_id}/branch-roles/{assignment_id}",
                    "admin",
                    (200, 204),
                    branch=None,
                )

        self.call(t, "employees list", "GET", "/api/v1/auth/employees", "admin", 200, branch=None)
        self.call(
            t,
            "employee directory",
            "GET",
            "/api/v1/auth/employees/directory",
            "reception",
            200,
            branch=None,
        )
        departments = (
            self.data(self.http.get("/api/v1/departments", headers=self._auth_header("admin")))
            or []
        )
        if departments:
            self.call(
                t,
                "employee create (fixed QA code)",
                "POST",
                "/api/v1/auth/employees",
                "admin",
                (201, 409),
                branch=None,
                json={
                    "email": "qa.emp.fixed@example.com",
                    "fullName": "QA Employee Fixed",
                    "employeeCode": "QA-EMP-FIXED",
                    "departmentId": departments[0]["id"],
                },
            )
        # The sync is a full, authoritative batch: re-send the current
        # directory unchanged so nothing gets deactivated.
        employees = (
            self.data(
                self.http.get(
                    "/api/v1/auth/employees",
                    params={"pageSize": 100},
                    headers=self._auth_header("admin"),
                )
            )
            or []
        )
        batch = [
            {
                "email": e["email"],
                "fullName": e["fullName"],
                "employeeCode": e["employeeCode"],
                "departmentId": e.get("departmentId"),
                "designation": e.get("designation"),
                "phoneNumber": e.get("phoneNumber"),
            }
            for e in employees
            if e.get("employeeCode") and e.get("isActive", True)
        ]
        if batch and len(batch) == len([e for e in employees if e.get("employeeCode")]):
            sync = self.call(
                t,
                "employee sync (unchanged batch)",
                "POST",
                "/api/v1/auth/employees/sync",
                "admin",
                200,
                branch=None,
                json={"employees": batch},
            )
            deactivated = (self.data(sync) or {}).get("deactivated")
            if deactivated:
                self.results[-1].ok = False
                self.results[-1].detail = f"unchanged batch deactivated {deactivated}"

    def _user_id_by_email(self, email: str) -> str | None:
        response = self.http.get(
            "/api/v1/auth/employees/directory",
            params={"search": email},
            headers=self._auth_header("admin"),
        )
        for row in self.data(response) or []:
            if row.get("email") == email:
                return row.get("id")
        return None

    def login_and_rate_limit(self, check_rate_limit: bool) -> None:
        """Last of the auth checks: the login limiter is 3/minute per IP, so
        the three real login cases come first and a fourth must trip it."""
        t = "auth"
        ok = self.call(
            t,
            "admin password login",
            "POST",
            "/api/v1/auth/login",
            None,
            200,
            branch=None,
            json={"email": "admin@example.com", "password": "admin12345"},
        )
        token = (self.data(ok) or {}).get("accessToken")
        if token:
            self.call(
                t,
                "logout (fresh session)",
                "POST",
                "/api/v1/auth/logout",
                None,
                (200, 204),
                branch=None,
                headers={"Authorization": f"Bearer {token}"},
                json={"refreshToken": (self.data(ok) or {}).get("refreshToken")},
            )
        self.call(
            t,
            "wrong password",
            "POST",
            "/api/v1/auth/login",
            None,
            401,
            branch=None,
            json={"email": "admin@example.com", "password": "wrong-password"},
        )
        self.call(
            t,
            "non-admin password login refused (SSO only)",
            "POST",
            "/api/v1/auth/login",
            None,
            403,
            branch=None,
            json={"email": "qa.created@example.com", "password": "qa-created-12345"},
        )
        if check_rate_limit:
            self.call(
                "rate-limit",
                "4th login in a minute is limited",
                "POST",
                "/api/v1/auth/login",
                None,
                429,
                branch=None,
                json={"email": "admin@example.com", "password": "wrong-password"},
            )

    def tenants(self) -> None:
        self.call(
            "tenants", "tenant profile", "GET", "/api/v1/tenants/me", "admin", 200, branch=None
        )
        self.call(
            "tenants",
            "tenant profile without token",
            "GET",
            "/api/v1/tenants/me",
            None,
            401,
            branch=None,
        )

    def platform(self) -> None:
        t = "platform"
        if "superadmin" in self.tokens:
            self.call(
                t, "tenants list", "GET", "/api/v1/platform/tenants", "superadmin", 200, branch=None
            )
        self.call(
            t,
            "tenants list with tenant token",
            "GET",
            "/api/v1/platform/tenants",
            "admin",
            (401, 403),
            branch=None,
        )
        # Never creates a tenant: the local DB keeps only the default one.
        self.call(
            t,
            "tenant create without token",
            "POST",
            "/api/v1/platform/tenants",
            None,
            (401, 403),
            branch=None,
            json={"name": "QA Nope", "slug": "qa-nope"},
        )
        self.call(
            t,
            "superadmin wrong password",
            "POST",
            "/api/v1/platform/auth/login",
            None,
            401,
            branch=None,
            json={"email": "qa.super@example.com", "password": "wrong"},
        )

    def org_structure(self) -> None:
        t = "org-structure"
        self.call(t, "company get", "GET", "/api/v1/company", "admin", 200, branch=None)
        self.call(
            t,
            "company get (reception)",
            "GET",
            "/api/v1/company",
            "reception",
            (200, 403),
            branch=None,
        )
        self.call(
            t,
            "company update (no-op)",
            "PUT",
            "/api/v1/company",
            "admin",
            200,
            branch=None,
            json={},
        )
        self.call(
            t,
            "company delete denied (reception)",
            "DELETE",
            "/api/v1/company",
            "reception",
            403,
            branch=None,
        )
        self.call(t, "branches list", "GET", "/api/v1/branches", "admin", 200, branch=None)
        self.call(t, "current branch", "GET", "/api/v1/branches/current", "reception", 200)
        self.call(
            t,
            "branch create denied (reception)",
            "POST",
            "/api/v1/branches",
            "reception",
            403,
            branch=None,
            json={"name": "QA Nope", "code": "QA-NOPE"},
        )
        self.call(
            t,
            "branch provision denied (host)",
            "POST",
            "/api/v1/branches/provision",
            "host",
            403,
            branch=None,
            json={"name": "QA Nope", "code": "QA-NOPE"},
        )

        code = f"QR{self.run_tag}"
        branch = self.call(
            t,
            "branch create",
            "POST",
            "/api/v1/branches",
            "admin",
            201,
            branch=None,
            json={"name": f"QA Run Branch {self.run_tag}", "code": code},
        )
        branch_id = self.id_of(branch)
        if not branch_id:
            return
        self.call(
            t, "branch get", "GET", f"/api/v1/branches/{branch_id}", "admin", 200, branch=None
        )
        self.call(
            t,
            "branch update",
            "PUT",
            f"/api/v1/branches/{branch_id}",
            "admin",
            200,
            branch=None,
            json={"city": "QA City"},
        )
        building_id = self.id_of(
            self.call(
                t,
                "building create",
                "POST",
                "/api/v1/buildings",
                "admin",
                201,
                branch=None,
                json={
                    "branchId": branch_id,
                    "name": f"QA Run Tower {self.run_tag}",
                    "code": f"B{code}",
                },
            )
        )
        floor_id = department_id = desk_id = gate_id = None
        if building_id:
            self.call(
                t,
                "building get",
                "GET",
                f"/api/v1/buildings/{building_id}",
                "admin",
                200,
                branch=None,
            )
            self.call(
                t,
                "building update",
                "PUT",
                f"/api/v1/buildings/{building_id}",
                "admin",
                200,
                branch=None,
                json={"address": "QA street"},
            )
            self.call(t, "buildings list", "GET", "/api/v1/buildings", "reception", 200)
            floor_id = self.id_of(
                self.call(
                    t,
                    "floor create",
                    "POST",
                    "/api/v1/floors",
                    "admin",
                    201,
                    branch=None,
                    json={"buildingId": building_id, "name": "QA Ground", "floorNumber": 0},
                )
            )
        if floor_id:
            self.call(
                t, "floor get", "GET", f"/api/v1/floors/{floor_id}", "admin", 200, branch=None
            )
            self.call(
                t,
                "floor update",
                "PUT",
                f"/api/v1/floors/{floor_id}",
                "admin",
                200,
                branch=None,
                json={"name": "QA Ground Floor"},
            )
            self.call(t, "floors list", "GET", "/api/v1/floors", "admin", 200, branch=None)
            department_id = self.id_of(
                self.call(
                    t,
                    "department create",
                    "POST",
                    "/api/v1/departments",
                    "admin",
                    201,
                    branch=None,
                    json={
                        "branchId": branch_id,
                        "floorId": floor_id,
                        "name": f"QA Run Dept {self.run_tag}",
                        "code": f"D{code}",
                    },
                )
            )
            desk_id = self.id_of(
                self.call(
                    t,
                    "reception desk create",
                    "POST",
                    "/api/v1/reception-desks",
                    "admin",
                    201,
                    branch=None,
                    json={"floorId": floor_id, "name": "QA Desk", "code": f"K{code}"},
                )
            )
        gate_id = self.id_of(
            self.call(
                t,
                "security gate create",
                "POST",
                "/api/v1/security-gates",
                "admin",
                201,
                branch=None,
                json={
                    "branchId": branch_id,
                    "buildingId": building_id,
                    "name": "QA Gate",
                    "code": f"G{code}",
                    "gateType": "entry",
                },
            )
        )
        for kind, path, entity_id, update in (
            ("department", "departments", department_id, {"name": f"QA Run Dept {self.run_tag}!"}),
            ("reception desk", "reception-desks", desk_id, {"name": "QA Desk 2"}),
            ("security gate", "security-gates", gate_id, {"name": "QA Gate 2"}),
        ):
            if entity_id:
                self.call(
                    t,
                    f"{kind} get",
                    "GET",
                    f"/api/v1/{path}/{entity_id}",
                    "admin",
                    200,
                    branch=None,
                )
                self.call(
                    t,
                    f"{kind} update",
                    "PUT",
                    f"/api/v1/{path}/{entity_id}",
                    "admin",
                    200,
                    branch=None,
                    json=update,
                )
                self.call(t, f"{kind}s list", "GET", f"/api/v1/{path}", "admin", 200, branch=None)
        self.call(
            t,
            "branch delete with active children refused",
            "DELETE",
            f"/api/v1/branches/{branch_id}",
            "admin",
            409,
            branch=None,
        )
        for kind, path, entity_id in (
            ("security gate", "security-gates", gate_id),
            ("reception desk", "reception-desks", desk_id),
            ("department", "departments", department_id),
            ("floor", "floors", floor_id),
            ("building", "buildings", building_id),
        ):
            if entity_id:
                self.call(
                    t,
                    f"{kind} delete",
                    "DELETE",
                    f"/api/v1/{path}/{entity_id}",
                    "admin",
                    (200, 204),
                    branch=None,
                )
        self.call(
            t,
            "branch delete",
            "DELETE",
            f"/api/v1/branches/{branch_id}",
            "admin",
            (200, 204),
            branch=None,
        )

    def kiosks_and_devices(self) -> None:
        t = "kiosks"
        kiosk_id = self.id_of(
            self.call(
                t,
                "kiosk create",
                "POST",
                "/api/v1/kiosks",
                "admin",
                201,
                json={"name": f"QA Kiosk {self.run_tag}"},
            )
        )
        self.call(
            t,
            "kiosk create denied (reception)",
            "POST",
            "/api/v1/kiosks",
            "reception",
            403,
            json={"name": "QA Nope"},
        )
        self.call(t, "kiosks list", "GET", "/api/v1/kiosks", "admin", 200)
        if kiosk_id:
            self.call(t, "kiosk get", "GET", f"/api/v1/kiosks/{kiosk_id}", "admin", 200)
            self.call(
                t,
                "kiosk update",
                "PUT",
                f"/api/v1/kiosks/{kiosk_id}",
                "admin",
                200,
                json={"description": "QA"},
            )
            self.call(
                t,
                "kiosk hide",
                "PATCH",
                f"/api/v1/kiosks/{kiosk_id}/visibility",
                "admin",
                200,
                json={"isHidden": True},
            )
            self.call(
                t, "kiosk delete", "DELETE", f"/api/v1/kiosks/{kiosk_id}", "admin", (200, 204)
            )

        t = "devices"
        device_id = f"qa-device-{self.run_tag.lower()}"
        registered = self.call(
            t,
            "device register (public)",
            "POST",
            "/api/v1/devices/register",
            None,
            (200, 201),
            branch=None,
            json={
                "name": f"QA Device {self.run_tag}",
                "deviceId": device_id,
                "branchId": self.branches["MAIN"],
                "operatingMode": "kiosk",
            },
        )
        self.call(
            t,
            "device approval status",
            "GET",
            "/api/v1/devices/approval-status",
            None,
            200,
            branch=None,
            params={"deviceId": device_id},
        )
        self.call(t, "devices list", "GET", "/api/v1/devices", "admin", 200)
        self.call(t, "devices list denied (host)", "GET", "/api/v1/devices", "host", 403)
        pk = self.id_of(registered)
        if pk:
            self.call(t, "device get", "GET", f"/api/v1/devices/{pk}", "admin", 200)
            self.call(t, "device approve", "POST", f"/api/v1/devices/{pk}/approve", "admin", 200)
            self.call(t, "device disable", "POST", f"/api/v1/devices/{pk}/disable", "admin", 200)
            self.call(t, "device enable", "POST", f"/api/v1/devices/{pk}/enable", "admin", 200)
            self.call(t, "device delete", "DELETE", f"/api/v1/devices/{pk}", "admin", (200, 204))
        setting = self.call(
            t,
            "kiosk location setting get",
            "GET",
            "/api/v1/admin/settings/kiosk-location-validation",
            "admin",
            200,
        )
        current = (self.data(setting) or {}).get("enforceKioskLocationValidation")
        if current is not None:
            self.call(
                t,
                "kiosk location setting put (unchanged)",
                "PUT",
                "/api/v1/admin/settings/kiosk-location-validation",
                "admin",
                200,
                json={"enforceKioskLocationValidation": current},
            )

    def visitor_types(self) -> None:
        t = "visitor-types"
        self.call(t, "categories list", "GET", "/api/v1/visitor-categories", "reception", 200)
        self.call(
            t,
            "category create denied (host)",
            "POST",
            "/api/v1/visitor-categories",
            "host",
            403,
            json={"name": "QA Nope", "code": "QA_NOPE"},
        )
        category_id = self.id_of(
            self.call(
                t,
                "category create",
                "POST",
                "/api/v1/visitor-categories",
                "admin",
                201,
                json={"name": f"QA Run Category {self.run_tag}", "code": f"QA_RUN_{self.run_tag}"},
            )
        )
        bulk = self.call(
            t,
            "categories bulk create",
            "POST",
            "/api/v1/visitor-categories/bulk",
            "admin",
            (200, 201),
            json={"names": [f"QA Bulk {self.run_tag}"]},
        )
        if category_id:
            self.call(
                t, "category get", "GET", f"/api/v1/visitor-categories/{category_id}", "admin", 200
            )
            self.call(
                t,
                "category update",
                "PUT",
                f"/api/v1/visitor-categories/{category_id}",
                "admin",
                200,
                json={"description": "QA run"},
            )
            roles = (
                self.data(
                    self.http.get(
                        "/api/v1/auth/roles",
                        params={"pageSize": 100},
                        headers=self._auth_header("admin"),
                    )
                )
                or []
            )
            reception_role = next(r["id"] for r in roles if r["name"] == "reception")
            rule_id = self.id_of(
                self.call(
                    t,
                    "workflow rule create",
                    "POST",
                    "/api/v1/approval-workflow-rules",
                    "admin",
                    201,
                    json={
                        "visitorCategoryId": category_id,
                        "stepOrder": 1,
                        "approverRoleId": reception_role,
                    },
                )
            )
            self.call(
                t, "workflow rules list", "GET", "/api/v1/approval-workflow-rules", "admin", 200
            )
            # Branch-scoped Reception reads the workflow it approves against.
            self.call(
                t,
                "workflow rules list (branch-scoped reception)",
                "GET",
                "/api/v1/approval-workflow-rules",
                "reception",
                200,
            )
            if rule_id:
                self.call(
                    t,
                    "workflow rule get",
                    "GET",
                    f"/api/v1/approval-workflow-rules/{rule_id}",
                    "admin",
                    200,
                )
                self.call(
                    t,
                    "workflow rule update",
                    "PUT",
                    f"/api/v1/approval-workflow-rules/{rule_id}",
                    "admin",
                    200,
                    json={"escalationMinutes": 30},
                )
                self.call(
                    t,
                    "workflow rule delete",
                    "DELETE",
                    f"/api/v1/approval-workflow-rules/{rule_id}",
                    "admin",
                    (200, 204),
                )
            self.call(
                t,
                "category delete",
                "DELETE",
                f"/api/v1/visitor-categories/{category_id}",
                "admin",
                (200, 204),
            )
        for item in (self.data(bulk) or {}).get("items", []):
            if item.get("category"):
                self.call(
                    t,
                    "bulk category delete",
                    "DELETE",
                    f"/api/v1/visitor-categories/{item['category']['id']}",
                    "admin",
                    (200, 204),
                )

    def form_builder(self) -> None:
        # Writes go to the QA form-builder branch only — never MAIN's live form.
        t, b = "form-builder", "QAFB"
        self.call(
            t, "effective form (MAIN)", "GET", "/api/v1/form-builder/effective", "reception", 200
        )
        self.call(t, "steps list", "GET", "/api/v1/form-builder/steps", "admin", 200, branch=b)
        self.call(
            t,
            "step create denied (host)",
            "POST",
            "/api/v1/form-builder/steps",
            "host",
            403,
            branch=b,
            json={"key": "qa_nope", "name": "QA Nope"},
        )
        step_id = self.id_of(
            self.call(
                t,
                "step create",
                "POST",
                "/api/v1/form-builder/steps",
                "admin",
                201,
                branch=b,
                json={"key": f"qa_run_{self.run_tag.lower()}", "name": f"QA Run {self.run_tag}"},
            )
        )
        if not step_id:
            return
        self.call(
            t,
            "step update",
            "PATCH",
            f"/api/v1/form-builder/steps/{step_id}",
            "admin",
            200,
            branch=b,
            json={"name": f"QA Run {self.run_tag} (edited)"},
        )
        field_ids = []
        for key in ("qa_text_a", "qa_text_b"):
            field_id = self.id_of(
                self.call(
                    t,
                    f"field create {key}",
                    "POST",
                    f"/api/v1/form-builder/steps/{step_id}/fields",
                    "admin",
                    201,
                    branch=b,
                    json={
                        "key": f"{key}_{self.run_tag.lower()}",
                        "label": key,
                        "fieldType": "text",
                    },
                )
            )
            if field_id:
                field_ids.append(field_id)
        self.call(
            t,
            "fields list",
            "GET",
            f"/api/v1/form-builder/steps/{step_id}/fields",
            "admin",
            200,
            branch=b,
        )
        if field_ids:
            self.call(
                t,
                "field update",
                "PATCH",
                f"/api/v1/form-builder/fields/{field_ids[0]}",
                "admin",
                200,
                branch=b,
                json={"label": "QA edited"},
            )
            self.call(
                t,
                "fields reorder",
                "POST",
                f"/api/v1/form-builder/steps/{step_id}/fields/reorder",
                "admin",
                200,
                branch=b,
                json={"orderedIds": list(reversed(field_ids))},
            )
        group_id = self.id_of(
            self.call(
                t,
                "group create",
                "POST",
                f"/api/v1/form-builder/steps/{step_id}/groups",
                "admin",
                201,
                branch=b,
                json={"key": f"qa_grp_{self.run_tag.lower()}", "name": "QA Group"},
            )
        )
        self.call(
            t,
            "groups list",
            "GET",
            f"/api/v1/form-builder/steps/{step_id}/groups",
            "admin",
            200,
            branch=b,
        )
        if group_id:
            self.call(
                t,
                "group update",
                "PATCH",
                f"/api/v1/form-builder/groups/{group_id}",
                "admin",
                200,
                branch=b,
                json={"name": "QA Group 2"},
            )
            self.call(
                t,
                "groups reorder",
                "POST",
                f"/api/v1/form-builder/steps/{step_id}/groups/reorder",
                "admin",
                200,
                branch=b,
                json={"orderedIds": [group_id]},
            )
            self.call(
                t,
                "group delete",
                "DELETE",
                f"/api/v1/form-builder/groups/{group_id}",
                "admin",
                (200, 204),
                branch=b,
            )
        for field_id in field_ids:
            self.call(
                t,
                "field delete",
                "DELETE",
                f"/api/v1/form-builder/fields/{field_id}",
                "admin",
                (200, 204),
                branch=b,
            )
        current = (
            self.data(
                self.http.get(
                    "/api/v1/form-builder/steps",
                    headers={**self._auth_header("admin"), "X-Branch-ID": self.branches[b]},
                )
            )
            or []
        )
        step_ids = [s["id"] for s in current]
        self.call(
            t,
            "steps reorder (unchanged order)",
            "POST",
            "/api/v1/form-builder/steps/reorder",
            "admin",
            200,
            branch=b,
            json={"orderedIds": step_ids},
        )
        self.call(
            t,
            "step delete",
            "DELETE",
            f"/api/v1/form-builder/steps/{step_id}",
            "admin",
            (200, 204),
            branch=b,
        )
        self.call(
            t,
            "publish (QA branch)",
            "POST",
            "/api/v1/form-builder/publish",
            "admin",
            (200, 201),
            branch=b,
        )

    def invitations_and_approvals(self) -> None:
        t = "invitations"
        # Lifecycle on QA_MULTI: create (host) -> reception step -> delegated
        # host step -> public check-in by tracking id -> security check-out.
        key = f"qa-idem-{self.run_tag}"
        lifecycle = self.create_invitation("lifecycle", "host", idempotency_key=key)
        if lifecycle:
            retry = self.call(
                t,
                "create retried with same Idempotency-Key",
                "POST",
                "/api/v1/invitations",
                "host",
                (200, 201),
                headers={"Idempotency-Key": key},
                data={
                    "payload": json.dumps(self.invitation_payload("lifecycle", category="QA_MULTI"))
                },
                files={"primary_contact_id_proof_file": ("id.jpg", self.jpeg(), "image/jpeg")},
            )
            if self.id_of(retry) and self.id_of(retry) != lifecycle["id"]:
                self.results[-1].ok = False
                self.results[-1].detail = "idempotent retry created a second invitation"
            inv_id, tracking = lifecycle["id"], lifecycle["trackingId"]
            self.call(t, "detail (admin)", "GET", f"/api/v1/invitations/{inv_id}", "admin", 200)
            # The creator isn't a "participant" until a step is delegated to
            # them (invitations spec, relevantToMe (a)-(e)) — F3.
            self.call(
                t,
                "detail hidden from creator host before delegation",
                "GET",
                f"/api/v1/invitations/{inv_id}",
                "host",
                404,
            )
            pending = self.invitation(inv_id) or {}
            step = pending.get("currentApprovalStep") or {}
            if step:
                self.call(
                    "approvals",
                    "host cannot approve reception step",
                    "POST",
                    f"/api/v1/invitations/{inv_id}/approval-steps/{step['id']}/approve",
                    "approver",
                    403,
                    json={},
                )
            self.call(
                t,
                "check-in before approval refused",
                "PATCH",
                f"/api/v2/invitations/{tracking}/check-in",
                None,
                (400, 409, 422),
                branch=None,
            )
            if self.approve_fully(inv_id):
                self.call(
                    t,
                    "detail visible to delegated approver",
                    "GET",
                    f"/api/v1/invitations/{inv_id}",
                    "approver",
                    200,
                )
                self.call(
                    t,
                    "public track by tracking id",
                    "GET",
                    "/api/v1/invitations/track",
                    None,
                    200,
                    branch=None,
                    params={"trackingId": tracking},
                )
                self.call(
                    t,
                    "check-in by tracking id (public)",
                    "PATCH",
                    f"/api/v2/invitations/{tracking}/check-in",
                    None,
                    200,
                    branch=None,
                )
                self.call(
                    t,
                    "repeat check-in is a no-op",
                    "PATCH",
                    f"/api/v2/invitations/{tracking}/check-in",
                    None,
                    200,
                    branch=None,
                )
                self.call(
                    t,
                    "badge",
                    "POST",
                    f"/api/v1/invitations/{inv_id}/badge",
                    "reception",
                    (200, 201),
                )
                self.call(
                    t,
                    "badge reprint",
                    "POST",
                    f"/api/v1/invitations/{inv_id}/badge/reprint",
                    "reception",
                    (200, 201),
                )
                self.call(
                    t,
                    "check-out",
                    "PATCH",
                    f"/api/v1/invitations/{inv_id}/check-out",
                    "security",
                    200,
                    json={},
                )
                final = self.invitation(inv_id) or {}
                if final.get("status") != "checked_out":
                    self.results[-1].ok = False
                    self.results[-1].detail = f"status after check-out: {final.get('status')}"
                self.file_storage(inv_id)

        # Status transitions on their own invitations.
        single = self.create_invitation("single", "reception", category="QA_SINGLE")
        if single:
            sid = single["id"]
            self.call(t, "QA_SINGLE detail", "GET", f"/api/v1/invitations/{sid}", "reception", 200)
            # Even with no workflow rules every invitation carries the step-0
            # ownership step, so it's approved through that step.
            self.approve_fully(sid, tag=t)
            self.call(
                t,
                "extend",
                "PATCH",
                f"/api/v1/invitations/{sid}/extend",
                "reception",
                200,
                json={"expiresAt": (datetime.now(UTC) + timedelta(days=2)).isoformat()},
            )
            self.call(
                t,
                "revert approval",
                "PATCH",
                f"/api/v1/invitations/{sid}/revert-approval",
                "reception",
                200,
                json={"reason": "QA revert"},
            )
        to_deny = self.create_invitation("deny", "host")
        if to_deny:
            self.call(
                t,
                "deny",
                "PATCH",
                f"/api/v1/invitations/{to_deny['id']}/deny",
                "reception",
                200,
                json={"reason": "QA deny"},
            )
            self.call(
                t,
                "deny twice refused",
                "PATCH",
                f"/api/v1/invitations/{to_deny['id']}/deny",
                "reception",
                (400, 409),
                json={"reason": "QA deny again"},
            )
        to_reject = self.create_invitation("reject", "host")
        if to_reject:
            step = (self.invitation(to_reject["id"]) or {}).get("currentApprovalStep") or {}
            if step:
                self.call(
                    "approvals",
                    "reject step",
                    "POST",
                    f"/api/v1/invitations/{to_reject['id']}/approval-steps/{step['id']}/reject",
                    "reception",
                    200,
                    json={"reason": "QA reject"},
                )
        to_edit = self.create_invitation("edit", "host")
        if to_edit:
            eid = to_edit["id"]
            self.call(
                t,
                "edit",
                "PATCH",
                f"/api/v1/invitations/{eid}/edit",
                "reception",
                200,
                json={"purposeOfVisit": "QA regression edited"},
            )
            self.call(
                t,
                "reschedule",
                "PATCH",
                f"/api/v1/invitations/{eid}/reschedule",
                "reception",
                200,
                json={
                    "preferredVisitDate": str(date.today() + timedelta(days=1)),
                    "preferredVisitTime": "11:00:00",
                },
            )
            self.call(
                t,
                "direct approve refused when a workflow exists",
                "POST",
                f"/api/v1/invitations/{eid}/approve",
                "admin",
                409,
                json={},
            )
            self.call(
                t,
                "watchlist override when not flagged",
                "POST",
                f"/api/v1/invitations/{eid}/watchlist-override",
                "admin",
                (400, 409),
                json={"reason": "QA override"},
            )

        # Lists, filters, export, lookups.
        for role in ("admin", "reception", "security"):
            self.call(t, "list", "GET", "/api/v1/invitations", role, 200)
        for role in ("host", "approver"):
            self.call(
                t, "branch-wide list denied (host role)", "GET", "/api/v1/invitations", role, 403
            )
            self.call(
                t,
                "relevant-to-me list",
                "GET",
                "/api/v1/invitations",
                role,
                200,
                params={"relevantToMe": "true"},
            )
        self.call(
            t,
            "list filtered + sorted",
            "GET",
            "/api/v1/invitations",
            "reception",
            200,
            params={
                "status": "approved",
                "sortBy": "submitted_at",
                "sortOrder": "desc",
                "page": 1,
                "pageSize": 20,
                "search": "QA",
            },
        )
        self.call(
            t,
            "list pageSize over max rejected",
            "GET",
            "/api/v1/invitations",
            "reception",
            422,
            params={"pageSize": 101},
        )
        self.call(
            t,
            "list bad sortBy rejected",
            "GET",
            "/api/v1/invitations",
            "reception",
            422,
            params={"sortBy": "hashed_password"},
        )
        self.call(t, "list denied (no role)", "GET", "/api/v1/invitations", "norole", 403)
        self.call(
            t,
            "export csv",
            "GET",
            "/api/v1/invitations/export",
            "reception",
            200,
            envelope=False,
            params={"format": "csv"},
        )
        self.call(
            t,
            "export denied (host)",
            "GET",
            "/api/v1/invitations/export",
            "host",
            403,
            params={"format": "csv"},
        )
        self.call(
            t,
            "lookup by email",
            "GET",
            "/api/v1/invitations/lookup-by-email",
            "reception",
            200,
            params={"email": f"qa.visitor.single{self.run_tag.lower()}@example.com"},
        )
        self.call(
            t,
            "QR check-in with bad token",
            "PATCH",
            "/api/v2/invitations/qr/not-a-real-token/check-in",
            None,
            (400, 401, 404),
            branch=None,
        )
        self.call(
            t,
            "QR check-out with bad token",
            "PATCH",
            "/api/v2/invitations/qr/not-a-real-token/check-out",
            None,
            (400, 401, 404),
            branch=None,
        )

        # Branch scoping: QA-B-only reception against MAIN.
        if lifecycle:
            self.call(
                t,
                "QA-B reception lists MAIN (X-Branch-ID MAIN) denied",
                "GET",
                "/api/v1/invitations",
                "branchb",
                403,
                branch="MAIN",
            )
            self.call(
                t,
                "QA-B reception reads MAIN invitation denied",
                "GET",
                f"/api/v1/invitations/{lifecycle['id']}",
                "branchb",
                (403, 404),
                branch="QA-B",
            )
        self.call(
            t,
            "QA-B reception lists own branch",
            "GET",
            "/api/v1/invitations",
            "branchb",
            200,
            branch="QA-B",
        )
        self.call(
            t,
            "host create in another branch denied",
            "POST",
            "/api/v1/invitations",
            "host",
            403,
            branch="QA-B",
            data={
                "payload": json.dumps(
                    self.invitation_payload("xbranch", category="QA_MULTI", branch="QA-B")
                )
            },
            files={"primary_contact_id_proof_file": ("id.jpg", self.jpeg(), "image/jpeg")},
        )

    def file_storage(self, invitation_id: str) -> None:
        detail = self.invitation(invitation_id) or {}
        urls = [detail.get("primaryContactIdProofUrl"), detail.get("primaryContactPhotoUrl")]
        urls += [v.get("idProofUrl") for v in detail.get("visitors") or []]
        url = next((u for u in urls if u and "/files/local/" in u), None)
        if url is None:
            return
        path = url[url.index("/api/v1/") :]
        self.call(
            "file-storage",
            "signed file download",
            "GET",
            path,
            None,
            200,
            branch=None,
            envelope=False,
        )
        self.call(
            "file-storage",
            "tampered signature refused",
            "GET",
            path.replace("sig=", "sig=00"),
            None,
            (401, 403),
            branch=None,
        )

    def registrations(self) -> None:
        t = "registrations"
        payload = self.invitation_payload("walkin", category="QA_SINGLE")
        payload["visitDetails"]["branchId"] = payload.pop("branchId")
        payload["visitDetails"]["buildingId"] = payload.pop("buildingId")
        self.call(
            t,
            "walk-in (default kiosk branch)",
            "POST",
            "/api/v1/registrations/walk-in",
            None,
            201,
            branch=None,
            data={"payload": json.dumps(payload)},
            files={"primary_contact_id_proof_file": ("id.jpg", self.jpeg(), "image/jpeg")},
        )
        self.call(
            t,
            "walk-in with bad device key",
            "POST",
            "/api/v1/registrations/walk-in",
            None,
            401,
            branch=None,
            headers={"X-Device-Key": "not-a-key"},
            data={"payload": json.dumps(payload)},
            files={"primary_contact_id_proof_file": ("id.jpg", self.jpeg(), "image/jpeg")},
        )

    def reads(self) -> None:
        self.call(
            "reports",
            "branch rollup",
            "GET",
            "/api/v1/reports/branches/rollup",
            "admin",
            200,
            branch=None,
        )
        self.call(
            "reports",
            "branch rollup denied (host)",
            "GET",
            "/api/v1/reports/branches/rollup",
            "host",
            403,
            branch=None,
        )
        t = "dashboard"
        self.call(
            t, "overview", "GET", "/api/v1/admin/dashboard/overview", "admin", 200, branch=None
        )
        self.call(
            t,
            "overview for branch",
            "GET",
            "/api/v1/admin/dashboard/overview",
            "admin",
            200,
            branch=None,
            params={"branchId": self.branches["MAIN"]},
        )
        self.call(
            t,
            "my overview (host)",
            "GET",
            "/api/v1/admin/dashboard/my-overview",
            "host",
            200,
            branch=None,
        )
        self.call(
            t,
            "my overview (reception)",
            "GET",
            "/api/v1/admin/dashboard/my-overview",
            "reception",
            200,
            branch=None,
        )
        self.call(
            t,
            "check-ins",
            "GET",
            "/api/v1/admin/dashboard/checkins",
            "admin",
            200,
            branch=None,
            params={"page": 1, "pageSize": 20},
        )
        self.call(
            t,
            "search",
            "GET",
            "/api/v1/admin/dashboard/search",
            "admin",
            200,
            branch=None,
            params={"query": "QA"},
        )
        self.call(
            t,
            "overview denied (no role)",
            "GET",
            "/api/v1/admin/dashboard/overview",
            "norole",
            403,
            branch=None,
        )
        t = "audit-trail"
        listing = self.call(
            t,
            "list",
            "GET",
            "/api/v1/audit-trail",
            "admin",
            200,
            branch=None,
            params={"page": 1, "pageSize": 5, "sortOrder": "desc"},
        )
        self.call(
            t,
            "list denied (reception)",
            "GET",
            "/api/v1/audit-trail",
            "reception",
            403,
            branch=None,
        )
        rows = self.data(listing) or []
        if rows:
            self.call(
                t, "get", "GET", f"/api/v1/audit-trail/{rows[0]['id']}", "admin", 200, branch=None
            )
        job = self.call(
            t,
            "report request",
            "POST",
            "/api/v1/audit-trail/reports",
            "admin",
            (200, 201, 202),
            branch=None,
            json={
                "formats": ["csv"],
                "createdAfter": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )
        job_id = self.id_of(job)
        if job_id:
            status = None
            for _ in range(30):
                polled = self.http.get(
                    f"/api/v1/audit-trail/reports/{job_id}", headers=self._auth_header("admin")
                )
                status = (self.data(polled) or {}).get("status")
                if status in ("ready", "completed", "failed"):
                    break
                time.sleep(1)
            self.call(
                t,
                "report status",
                "GET",
                f"/api/v1/audit-trail/reports/{job_id}",
                "admin",
                200,
                branch=None,
            )
            if status not in ("ready", "completed"):
                self.results[-1].ok = False
                self.results[-1].detail = f"report job did not complete in 30s (status={status})"
            else:
                self.call(
                    t,
                    "report download",
                    "GET",
                    f"/api/v1/audit-trail/reports/{job_id}/download",
                    "admin",
                    (200, 307),
                    branch=None,
                    envelope=False,
                    params={"format": "csv"},
                )

    def public_and_visitor(self) -> None:
        t = "visit-info"
        self.call(
            t,
            "host search",
            "GET",
            "/api/v1/hosts/search",
            None,
            200,
            branch=None,
            params={"query": "QA"},
        )
        self.call(t, "departments", "GET", "/api/v1/visit-info/departments", None, 200, branch=None)
        self.call(t, "options", "GET", "/api/v1/visit-info/options", None, 200, branch=None)
        t = "identity-verification"
        self.call(
            t,
            "OTP request",
            "POST",
            "/api/v1/identity-verification/otp/request",
            None,
            (200, 202),
            branch=None,
            json={"identifier": f"qa.otp.{self.run_tag.lower()}@example.com", "channel": "email"},
        )
        self.call(
            t,
            "OTP verify wrong code",
            "POST",
            "/api/v1/identity-verification/otp/verify",
            None,
            (400, 401),
            branch=None,
            json={
                "identifier": f"qa.otp.{self.run_tag.lower()}@example.com",
                "channel": "email",
                "code": "000000",
            },
        )
        t = "visitor-portal"
        self.call(
            t,
            "me (verified visitor)",
            "GET",
            "/api/v1/visitor-portal/me",
            "visitor",
            200,
            branch=None,
        )
        self.call(
            t,
            "me with staff token refused",
            "GET",
            "/api/v1/visitor-portal/me",
            "reception",
            401,
            branch=None,
        )
        t = "email-assets"
        self.call(
            t,
            "logo",
            "GET",
            "/api/v1/public/email-assets/guestify-logo.png",
            None,
            200,
            branch=None,
            envelope=False,
        )
        self.call(
            t,
            "QR image with bad signature",
            "GET",
            f"/api/v1/public/email-assets/{self.tokens['tenantId']}/qr/{uuid.uuid4()}.png",
            None,
            (401, 403, 404),
            branch=None,
            params={"exp": "1", "sig": "bad"},
        )
        t = "notifications"
        fcm = f"qa-fcm-{self.run_tag.lower()}"
        self.call(
            t,
            "register push device",
            "POST",
            "/api/v1/notifications/devices",
            "host",
            (200, 201),
            branch=None,
            json={"fcmToken": fcm, "platform": "web"},
        )
        self.call(
            t,
            "unregister push device",
            "DELETE",
            f"/api/v1/notifications/devices/{fcm}",
            "host",
            (200, 204),
            branch=None,
        )

    def sso(self) -> None:
        t = "sso"
        self.call(
            t, "config get", "GET", "/api/v1/auth/sso/config", "admin", (200, 404), branch=None
        )
        self.call(
            t,
            "config get denied (reception)",
            "GET",
            "/api/v1/auth/sso/config",
            "reception",
            403,
            branch=None,
        )
        self.call(
            t, "role mappings", "GET", "/api/v1/auth/sso/role-mappings", "admin", 200, branch=None
        )
        roles = (
            self.data(
                self.http.get(
                    "/api/v1/auth/roles",
                    params={"pageSize": 100},
                    headers=self._auth_header("admin"),
                )
            )
            or []
        )
        host_role = next(r["id"] for r in roles if r["name"] == "host")
        mapping_id = self.id_of(
            self.call(
                t,
                "role mapping create",
                "POST",
                "/api/v1/auth/sso/role-mappings",
                "admin",
                201,
                branch=None,
                json={"idpGroupClaimValue": f"qa-run-{self.run_tag.lower()}", "roleId": host_role},
            )
        )
        if mapping_id:
            self.call(
                t,
                "role mapping delete",
                "DELETE",
                f"/api/v1/auth/sso/role-mappings/{mapping_id}",
                "admin",
                (200, 204),
                branch=None,
            )
        self.call(
            t,
            "login redirect",
            "GET",
            "/api/v1/auth/sso/default/login",
            None,
            (302, 303, 307, 404),
            branch=None,
            envelope=False,
        )
        self.call(
            t,
            "exchange bogus code",
            "POST",
            "/api/v1/auth/sso/exchange",
            None,
            (400, 401),
            branch=None,
            json={"code": "not-a-code"},
        )

    # --- coverage + report ------------------------------------------------

    def uncovered_tags(self) -> list[str]:
        spec = self.http.get("/openapi.json").json()
        tags = {
            (op.get("tags") or ["untagged"])[0]
            for ops in spec["paths"].values()
            for op in ops.values()
        }
        covered = {r.tag for r in self.results if r.ok and r.status is not None and r.status < 400}
        return sorted(tags - covered)


SCENARIOS: dict[str, Callable[[Runner], None]] = {
    "health": Runner.health,
    "auth": Runner.auth,
    "tenants": Runner.tenants,
    "platform": Runner.platform,
    "org-structure": Runner.org_structure,
    "kiosks": Runner.kiosks_and_devices,
    "visitor-types": Runner.visitor_types,
    "form-builder": Runner.form_builder,
    "invitations": Runner.invitations_and_approvals,
    "registrations": Runner.registrations,
    "reads": Runner.reads,
    "public": Runner.public_and_visitor,
    "sso": Runner.sso,
}


def print_summary(runner: Runner, uncovered: list[str]) -> None:
    failures = [r for r in runner.results if not r.ok and not r.known_issue]
    known = [r for r in runner.results if not r.ok and r.known_issue]
    stale = [r for r in runner.results if r.ok and r.known_issue]
    by_tag: dict[str, list[Result]] = {}
    for r in runner.results:
        by_tag.setdefault(r.tag, []).append(r)
    print(f"\n{'tag':<24}{'calls':>6}{'fail':>6}{'p50 ms':>9}{'max ms':>9}")
    for tag, rows in sorted(by_tag.items()):
        latencies = sorted(r.latency_ms for r in rows)
        p50 = latencies[len(latencies) // 2]
        failed = sum(not r.ok for r in rows)
        print(f"{tag:<24}{len(rows):>6}{failed:>6}{p50:>9.0f}{latencies[-1]:>9.0f}")
    print(
        f"\n{len(runner.results)} calls, {len(failures)} failures, {len(known)} known issues, "
        f"run tag {runner.run_tag}"
    )
    for r in known:
        print(f"KNOWN {r.known_issue} [{r.tag}] {r.name}: {r.method} {r.path} -> {r.status}")
    for r in stale:
        print(f"STALE known-issue entry {r.known_issue} [{r.tag}] {r.name} now passes — remove it")
    for r in failures:
        print(
            f"\nFAIL [{r.tag}] {r.name}: {r.method} {r.path} as {r.role} "
            f"-> {r.status} (expected {r.expected}, envelope_ok={r.envelope_ok}, "
            f"request_id={r.request_id})\n  {r.detail}"
        )
    if uncovered:
        print(f"\nUNCOVERED router tags (no passing happy-path call): {', '.join(uncovered)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--tokens", type=Path, default=TOKENS_PATH)
    parser.add_argument("--only", help="comma-separated scenario names: " + ",".join(SCENARIOS))
    parser.add_argument(
        "--skip-rate-limit",
        action="store_true",
        help="skip the login burst that trips the 3/minute limiter",
    )
    args = parser.parse_args()

    runner = Runner(args.base_url, json.loads(args.tokens.read_text()))
    runner.setup()
    selected = args.only.split(",") if args.only else list(SCENARIOS)
    # Login and the SSO endpoints allow 3/minute per IP: a full run that
    # finished within the last minute already spent that quota.
    if not args.only:
        elapsed = time.time() - (RUN_STAMP.stat().st_mtime if RUN_STAMP.exists() else 0)
        if elapsed < 61:
            print(f"Waiting {61 - elapsed:.0f}s for the rate-limit window...", file=sys.stderr)
            time.sleep(61 - elapsed)
    for name in selected:
        SCENARIOS[name](runner)
    if not args.only:
        runner.login_and_rate_limit(check_rate_limit=not args.skip_rate_limit)
        RUN_STAMP.touch()

    uncovered = runner.uncovered_tags() if not args.only else []
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "runTag": runner.run_tag,
                "finishedAt": datetime.now(UTC).isoformat(),
                "uncoveredTags": uncovered,
                "results": [asdict(r) for r in runner.results],
            },
            indent=1,
        )
    )
    print_summary(runner, uncovered)
    sys.exit(1 if uncovered or any(not r.ok and not r.known_issue for r in runner.results) else 0)


if __name__ == "__main__":
    main()
