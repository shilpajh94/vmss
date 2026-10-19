"""Load test for the hot read/write paths (openspec/changes/
full-stack-qa-and-load-testing, spec "Load test with a recorded baseline").

Local DDEV default tenant only, with pre-minted QA tokens (password login is
rate-limited and staff are SSO-only, so login itself isn't load-tested):

    ddev exec uv run python scripts/qa_regression/seed_qa_fixtures.py
    ddev exec uv run python scripts/qa_regression/mint_tokens.py
    # set RATE_LIMIT_ENABLED=false in .env for the run — see docs/features/qa-harness.md
    ddev exec uv run locust -f loadtests/locustfile.py --headless \\
        --host http://localhost:8000 --users 50 --spawn-rate 10 --run-time 5m \\
        --csv var/qa/load

The run exits non-zero when the aggregate p95 is 500 ms or more, the error
rate is 1% or more, or any request returned a 5xx. Every invitation it
creates is named `QA LOAD ...` so `scripts/qa_regression/reset_qa_data.py`
removes it.
"""

import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Any

import requests
from locust import HttpUser, between, events, task
from locust.env import Environment

TOKENS = json.loads(
    Path(os.environ.get("QA_TOKENS", Path(__file__).parents[1] / "var/qa/tokens.json")).read_text()
)
P95_LIMIT_MS = float(os.environ.get("LOAD_P95_LIMIT_MS", "500"))
ERROR_RATE_LIMIT = float(os.environ.get("LOAD_ERROR_RATE_LIMIT", "0.01"))
MAIN = TOKENS["branches"]["MAIN"]
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
_server_errors = 0
_tracking_ids: list[str] = []


def headers(role: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKENS['users'][role]['token']}",
        "X-Branch-ID": MAIN,
    }


class StaffUser(HttpUser):
    """Dashboards and invitation lists — the bulk of real portal traffic."""

    weight = 3
    wait_time = between(1, 3)

    @task(3)
    def reception_invitation_list(self) -> None:
        self.client.get(
            "/api/v1/invitations",
            params={"page": 1, "pageSize": 20, "sortBy": "submitted_at", "sortOrder": "desc"},
            headers=headers("reception"),
            name="GET /invitations (branch list)",
        )

    @task(2)
    def host_relevant_list(self) -> None:
        self.client.get(
            "/api/v1/invitations",
            params={"relevantToMe": "true", "pageSize": 20},
            headers=headers("approver"),
            name="GET /invitations?relevantToMe",
        )

    @task(2)
    def admin_overview(self) -> None:
        self.client.get(
            "/api/v1/admin/dashboard/overview",
            headers=headers("admin"),
            name="GET /dashboard/overview",
        )

    @task(2)
    def my_overview(self) -> None:
        self.client.get(
            "/api/v1/admin/dashboard/my-overview",
            headers=headers("reception"),
            name="GET /dashboard/my-overview",
        )

    @task(1)
    def checkins(self) -> None:
        self.client.get(
            "/api/v1/admin/dashboard/checkins",
            params={"page": 1, "pageSize": 20},
            headers=headers("admin"),
            name="GET /dashboard/checkins",
        )


class ReceptionUser(HttpUser):
    """The write path end to end: create (idempotent), approve the
    ownership step, gate check-in by tracking id, check-out."""

    weight = 2
    wait_time = between(2, 5)

    def on_start(self) -> None:
        # One-off reference data, fetched outside Locust's client so it
        # doesn't count towards the measured traffic.
        form = requests.get(
            f"{self.host}/api/v1/form-builder/effective", headers=headers("admin"), timeout=30
        ).json()["data"]
        fields = {f["key"]: f for step in form for f in step.get("fields", [])}
        self.consents = [
            {"fieldId": fields[k]["id"], "accepted": True}
            for k in ("terms_accepted", "data_processing_accepted", "safety_guidelines_accepted")
            if k in fields and fields[k].get("isActive", True)
        ]
        buildings = requests.get(
            f"{self.host}/api/v1/buildings", headers=headers("admin"), timeout=30
        ).json()["data"]
        self.building_id = next(b["id"] for b in buildings if b["branchId"] == MAIN)

    def _payload(self, tag: str) -> dict[str, Any]:
        return {
            "registrationType": "individual",
            "branchId": MAIN,
            "buildingId": self.building_id,
            "visitorCategoryId": TOKENS["categories"]["QA_SINGLE"],
            "primaryContact": {
                "fullName": f"QA LOAD {tag}",
                "email": f"qa.load.{tag.lower()}@example.com",
                "preferredContactMethod": "email",
            },
            "visitDetails": {
                "purposeOfVisit": "QA load test",
                "preferredVisitDate": str(datetime.date.today()),
                "preferredVisitTime": "10:00:00",
                "expectedDuration": "< 1 hour",
            },
            "consents": self.consents,
        }

    @task
    def visit_lifecycle(self) -> None:
        tag = uuid.uuid4().hex[:10].upper()
        created = self.client.post(
            "/api/v1/invitations",
            data={"payload": json.dumps(self._payload(tag))},
            files={"primary_contact_id_proof_file": ("id.jpg", JPEG, "image/jpeg")},
            headers={**headers("reception"), "Idempotency-Key": f"qa-load-{tag}"},
            name="POST /invitations",
        )
        if created.status_code != 201:
            return
        invitation = created.json()["data"]
        _tracking_ids.append(invitation["trackingId"])
        step = invitation.get("currentApprovalStep")
        if step:
            self.client.post(
                f"/api/v1/invitations/{invitation['id']}/approval-steps/{step['id']}/approve",
                json={},
                headers=headers("reception"),
                name="POST /approval-steps/{id}/approve",
            )
        self.client.patch(
            f"/api/v2/invitations/{invitation['trackingId']}/check-in",
            name="PATCH /v2/invitations/{trackingId}/check-in",
        )
        self.client.patch(
            f"/api/v1/invitations/{invitation['id']}/check-out",
            json={},
            headers=headers("reception"),
            name="PATCH /invitations/{id}/check-out",
        )


class PublicUser(HttpUser):
    """Unauthenticated visitor/kiosk lookups."""

    weight = 1
    wait_time = between(1, 3)

    @task(2)
    def track(self) -> None:
        if _tracking_ids:
            self.client.get(
                "/api/v1/invitations/track",
                params={"trackingId": _tracking_ids[-1]},
                name="GET /invitations/track",
            )

    @task(1)
    def visit_info_options(self) -> None:
        self.client.get("/api/v1/visit-info/options", name="GET /visit-info/options")


@events.request.add_listener
def _count_server_errors(response: Any = None, **_: Any) -> None:
    global _server_errors
    if response is not None and getattr(response, "status_code", 0) >= 500:
        _server_errors += 1


@events.quitting.add_listener
def _enforce_thresholds(environment: Environment, **_: Any) -> None:
    total = environment.stats.total
    if not total.num_requests:
        environment.process_exit_code = 1
        print("LOAD GATE FAIL: no requests were made")
        return
    p95 = total.get_response_time_percentile(0.95)
    error_rate = total.fail_ratio
    problems = []
    if p95 >= P95_LIMIT_MS:
        slow = [
            f"{e.method} {e.name} p95={e.get_response_time_percentile(0.95):.0f}ms"
            for e in environment.stats.entries.values()
            if e.get_response_time_percentile(0.95) >= P95_LIMIT_MS
        ]
        problems.append(f"aggregate p95 {p95:.0f}ms >= {P95_LIMIT_MS:.0f}ms ({'; '.join(slow)})")
    if error_rate >= ERROR_RATE_LIMIT:
        failing = [
            f"{e.method} {e.name} {e.num_failures}/{e.num_requests}"
            for e in environment.stats.entries.values()
            if e.num_failures
        ]
        problems.append(
            f"error rate {error_rate:.2%} >= {ERROR_RATE_LIMIT:.0%} ({'; '.join(failing)})"
        )
    if _server_errors:
        problems.append(f"{_server_errors} responses were 5xx")
    summary = (
        f"requests={total.num_requests} p50={total.median_response_time:.0f}ms "
        f"p95={p95:.0f}ms p99={total.get_response_time_percentile(0.99):.0f}ms "
        f"errors={error_rate:.2%} 5xx={_server_errors}"
    )
    if problems:
        environment.process_exit_code = 1
        print(f"LOAD GATE FAIL: {summary}\n  " + "\n  ".join(problems))
    else:
        environment.process_exit_code = 0
        print(f"LOAD GATE PASS: {summary}")
