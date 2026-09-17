"""Generates real, visible activity against the *actually running* dev API —
real confirmation/OTP emails landing in Mailpit, real rows landing in the
dev database — as a human-inspectable complement to the automated test
suite (openspec/changes/archive/.../add-celery-worker-and-demo-seed-script).

Unlike every other `scripts/*.py` (which call service/repository functions
directly, in-process), this one talks real HTTP to `--base-url` — the
entire point is to exercise the real HTTP layer, real Celery dispatch (see
that change's root-cause fix: a Celery worker must actually be running, via
`ddev restart` after this change lands), and real SMTP, not to shortcut
around them.

Prerequisite: `ddev exec uv run python scripts/seed_dev_data.py` must have
already been run at least once — it provisions the default tenant and the
`admin@example.com` account this script logs in as. This script does not
provision a tenant itself, to avoid a second, divergent bootstrap path.

Every run is additive, tagged with a fresh run id, and safe to re-run
repeatedly — each run visibly adds more data rather than becoming a no-op.

Usage: ddev exec uv run python scripts/seed_demo_workflow.py \
    [--base-url https://vmss-new-api.ddev.site:8443] \
    [--invitations 3] [--otp-requests 2]
"""

import argparse
import asyncio
import io
import json
import sys
import uuid

import httpx
from PIL import Image
from provision_registration_device import provision_device_key

from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine
from vmss_api.tenant.repository import TenantRepository

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin12345"


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _login(client: httpx.Client) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        print(
            f"Could not log in as {ADMIN_EMAIL!r} ({response.status_code}: {response.text}).\n"
            "Run `ddev exec uv run python scripts/seed_dev_data.py` first — this script "
            "does not provision a tenant/admin itself.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return response.json()["data"]["accessToken"]


def _individual_payload(full_name: str, email: str) -> dict:
    return {
        "registrationType": "individual",
        "primaryContact": {
            "fullName": full_name,
            "email": email,
            "preferredContactMethod": "email",
            "idProofType": "Passport",
        },
        "visitors": [],
        "visitDetails": {
            "purposeOfVisit": "Demo visit",
            "hostNameOrEmail": "reception@example.com",
            "preferredVisitDate": "2026-08-25",
            "preferredVisitTime": "10:00:00",
            "expectedDuration": "< 1 hour",
            "departmentToVisit": "Reception",
        },
        "carriedItems": {"items": []},
        "vehicles": [],
        "consents": {
            "terms_accepted": True,
            "data_processing_accepted": True,
            "safety_guidelines_accepted": True,
        },
    }


def _ensure_company(client: httpx.Client, run_tag: str) -> None:
    if client.get("/api/v1/company").status_code == 200:
        return
    response = client.post("/api/v1/company", json={"legalName": f"Demo Workflow Co ({run_tag})"})
    response.raise_for_status()


def _build_org_structure(client: httpx.Client, *, branch_id: str, run_tag: str) -> dict:
    _ensure_company(client, run_tag)

    building = client.post(
        "/api/v1/buildings",
        json={"branchId": branch_id, "name": f"Demo Tower {run_tag}", "code": f"TWR-{run_tag}"},
    )
    building.raise_for_status()
    building_id = building.json()["data"]["id"]

    floor = client.post(
        "/api/v1/floors",
        json={"buildingId": building_id, "name": "Ground Floor", "floorNumber": 0},
    )
    floor.raise_for_status()
    floor_id = floor.json()["data"]["id"]

    department = client.post(
        "/api/v1/departments",
        json={
            "branchId": branch_id,
            "floorId": floor_id,
            "name": f"Demo Department {run_tag}",
            "code": f"DEP-{run_tag}",
        },
    )
    department.raise_for_status()

    desk = client.post(
        "/api/v1/reception-desks",
        json={"floorId": floor_id, "name": "Demo Desk", "code": f"DESK-{run_tag}"},
    )
    desk.raise_for_status()

    gate = client.post(
        "/api/v1/security-gates",
        json={
            "branchId": branch_id,
            "buildingId": building_id,
            "name": "Demo Gate",
            "code": f"GATE-{run_tag}",
            "gateType": "entry",
        },
    )
    gate.raise_for_status()

    category = client.post(
        "/api/v1/visitor-categories",
        json={"name": f"Demo Visitor Category {run_tag}", "code": f"CAT-{run_tag}"},
    )
    category.raise_for_status()
    category_id = category.json()["data"]["id"]

    roles = client.get("/api/v1/auth/roles?pageSize=100")
    roles.raise_for_status()
    admin_role_id = next(r["id"] for r in roles.json()["data"] if r["name"] == "admin")

    rule = client.post(
        "/api/v1/approval-workflow-rules",
        json={"visitorCategoryId": category_id, "stepOrder": 1, "approverRoleId": admin_role_id},
    )
    rule.raise_for_status()

    return {"buildingId": building_id, "floorId": floor_id}


def _create_invitations(client: httpx.Client, *, count: int, run_tag: str) -> list[str]:
    tracking_ids = []
    for i in range(count):
        full_name = f"Demo Visitor {run_tag}-{i}"
        payload = _individual_payload(full_name, f"demo-{run_tag}-{i}@example.com")
        response = client.post(
            "/api/v1/invitations",
            data={"payload": json.dumps(payload)},
            files={"primary_contact_id_proof_file": ("id.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        response.raise_for_status()
        tracking_ids.append(response.json()["data"]["trackingId"])
    return tracking_ids


def _request_otps(client: httpx.Client, *, count: int, run_tag: str) -> list[str]:
    # Request only — never verify. The raw OTP code is stored only as an
    # HMAC hash (`identity_verification/service.py::_hash_code`), never in
    # plaintext, so nothing this script can reach could recover it to
    # complete the verify step even if it tried. Check Mailpit for the code.
    identifiers = []
    for i in range(count):
        identifier = f"demo-otp-{run_tag}-{i}@example.com"
        response = client.post(
            "/api/v1/identity-verification/otp/request",
            json={"identifier": identifier, "channel": "email"},
        )
        response.raise_for_status()
        identifiers.append(identifier)
    return identifiers


async def _provision_walk_in_device_key(*, tenant_id: uuid.UUID, branch_id: uuid.UUID) -> str:
    async with AsyncSessionLocal() as db:
        raw_key = await provision_device_key(
            db, tenant_id=tenant_id, branch_id=branch_id, label="seed_demo_workflow kiosk"
        )
        await db.commit()
        return raw_key


def _create_walk_in(client: httpx.Client, *, raw_device_key: str, run_tag: str) -> str:
    payload = _individual_payload(f"Demo Walk-In {run_tag}", f"demo-walkin-{run_tag}@example.com")
    response = client.post(
        "/api/v1/registrations/walk-in",
        data={"payload": json.dumps(payload)},
        files={"primary_contact_id_proof_file": ("id.jpg", _jpeg_bytes(), "image/jpeg")},
        headers={"X-Device-Key": raw_device_key},
    )
    response.raise_for_status()
    return response.json()["data"]["trackingId"]


async def _resolve_tenant_id() -> uuid.UUID:
    try:
        async with AsyncSessionLocal() as db:
            tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
            if tenant is None:
                print(
                    "No default tenant found — run "
                    "`ddev exec uv run python scripts/seed_dev_data.py` first.",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            return tenant.id
    finally:
        # This script calls `asyncio.run()` twice (here, and again for
        # `_provision_walk_in_device_key` below) — each creates its own
        # event loop, but `core/database.py::engine` is a single,
        # process-wide pooled `AsyncEngine`. Without disposing here, the
        # second call would try to reuse a connection bound to this
        # (about-to-close) loop and fail with "... attached to a different
        # loop" — the exact bug fixed in `invitations/tasks.py` for the
        # same reason (per-task `asyncio.run()` against one shared engine).
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://vmss-new-api.ddev.site:8443")
    parser.add_argument("--invitations", type=int, default=3)
    parser.add_argument("--otp-requests", type=int, default=2)
    args = parser.parse_args()

    run_tag = f"demo-{uuid.uuid4().hex[:8]}"
    tenant_id = asyncio.run(_resolve_tenant_id())

    with httpx.Client(base_url=args.base_url, verify=False, timeout=30.0) as client:
        token = _login(client)
        client.headers["Authorization"] = f"Bearer {token}"

        branches = client.get("/api/v1/branches")
        branches.raise_for_status()
        branch_id = branches.json()["data"][0]["id"]
        # `POST /invitations` resolves its branch from this header (or an
        # explicit `branchId` in the payload) — set once here so every
        # subsequent branch-scoped call in this run targets it.
        client.headers["X-Branch-ID"] = branch_id

        _build_org_structure(client, branch_id=branch_id, run_tag=run_tag)
        tracking_ids = _create_invitations(client, count=args.invitations, run_tag=run_tag)
        otp_identifiers = _request_otps(client, count=args.otp_requests, run_tag=run_tag)

        raw_device_key = asyncio.run(
            _provision_walk_in_device_key(tenant_id=tenant_id, branch_id=uuid.UUID(branch_id))
        )
        # The device key's client headers must NOT carry the admin bearer
        # token — this is meant to be an unauthenticated-by-user, device-
        # authenticated call, matching how a real kiosk would call it.
        with httpx.Client(base_url=args.base_url, verify=False, timeout=30.0) as anon_client:
            walk_in_tracking_id = _create_walk_in(
                anon_client, raw_device_key=raw_device_key, run_tag=run_tag
            )

    print(f"\nRun tag: {run_tag}")
    print(f"Logged in as: {ADMIN_EMAIL}")
    print(f"Invitations created ({len(tracking_ids)}): {', '.join(tracking_ids)}")
    print(f"OTP requests sent ({len(otp_identifiers)}): {', '.join(otp_identifiers)}")
    print(f"Walk-in registration created: {walk_in_tracking_id}")
    print(
        "\nCheck Mailpit now for the confirmation emails and OTP codes. If this is the "
        "first run since the Celery worker daemon was added, run `ddev restart` first — "
        "without it, invitation-confirmation emails will silently queue and never send."
    )


if __name__ == "__main__":
    main()
