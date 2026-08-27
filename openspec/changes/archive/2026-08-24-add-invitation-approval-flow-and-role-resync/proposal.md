## Why

Two integration-blocking issues were reported. First, every pre-registered
invitation is immediately treated as confirmed — `status="submitted"` is
hardcoded at creation and one email (tracking ID + QR code together) always
goes out — even though `Company.auto_approve_pre_registered_visitors`
already exists as tenant-wide config and is documented as "stored, not yet
read by any other feature." Clients need the QR/tracking email withheld
until a request is actually approved (automatically or by a human), per a
specific auto-approve-vs-manual-approve scenario. Second, an invitation
listing call is failing with "Insufficient permission" for a role that,
per the current permission catalog (`auth/rbac_catalog.py`), should already
hold `invitations:view` — the catalog is only ever applied to a tenant's
roles at provisioning time (`platform/service.py::create_tenant`), so a
tenant provisioned before a permission was added to the catalog has
permanently stale roles. This exact class of bug already happened once
before for `invitations:create` (per `rbac_catalog.py`'s own docstring) and
there is still no way to fix it without hand-editing the database.

## What Changes

- Invitation creation resolves `Company.auto_approve_pre_registered_visitors`
  (defaulting to "awaiting approval" if no `Company` profile is configured
  yet) instead of hardcoding `status="submitted"`:
  - **Auto-approve enabled**: `status="approved"` immediately; the
    dispatched email is the approval email (tracking ID + QR code).
  - **Auto-approve disabled**: `status="submitted"` ("awaiting approval");
    the dispatched email carries the tracking ID only — **no QR code**.
- **New**: `POST /invitations/{id}/approve` — transitions a `submitted`
  invitation to `approved` and dispatches the approval email (tracking ID +
  QR code) at that point. Gated by a **new** `invitations:approve`
  permission, granted by default to `admin`, `reception`, and `host`
  (mirroring `invitations:create`'s grant; `security` stays view-only).
  Approving an invitation not currently `submitted` (already approved, or
  not found/not authorized at its branch) is rejected — 409 or 404
  respectively. Reject/decline is explicitly **out of scope** for this
  change.
- `Invitation` gains an `approved_at` timestamp (nullable), set when status
  transitions to `approved` — by either path above.
- The single "visit confirmation" Celery task/email is split into two:
  a tracking-only notification (no QR) and an approval notification
  (QR + tracking) — dispatched depending on which of the two paths above
  produced the `approved`/`submitted` status.
- **New**: `POST /auth/roles/resync-permissions` — gated by the existing
  `roles:manage` permission, re-runs `rbac_catalog.py::seed_default_roles`'s
  union-merge against the *current* tenant's already-existing standard
  roles (Admin/Reception/Security/Host), backfilling any permission code
  the catalog says that role should have (including the new
  `invitations:approve`, and anything else added to the catalog since that
  tenant was provisioned) without ever removing a custom grant. Returns
  which permissions were newly granted to which roles.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `invitations`: creation's initial status and dispatched-email content now
  depend on `Company.auto_approve_pre_registered_visitors`; adds the
  `POST /invitations/{id}/approve` action.
- `auth`: adds an idempotent way to resync an existing tenant's standard
  roles' permissions against the current catalog, on top of the
  provisioning-time-only seeding that exists today.

## Impact

- **Code**: `src/vmss_api/invitations/{models,service,tasks,router,schemas}.py`
  (status/email-dispatch split, new approve action), `alembic_tenant/`
  (new `approved_at` column migration), `src/vmss_api/auth/rbac_catalog.py`
  (new `invitations:approve` permission code + default role grants),
  `src/vmss_api/auth/{service,router,schemas}.py` (new resync endpoint).
- **API contract**: new `POST /invitations/{id}/approve` and
  `POST /auth/roles/resync-permissions` endpoints. `POST /invitations`'s
  response `status` field may now be `submitted` or `approved` (previously
  always `submitted`); `GET /invitations`/`GET /invitations/track` expose
  the same two values plus the new `approvedAt` field.
- **Notifications**: the previously single "visit confirmation" email is
  now one of two distinct emails depending on approval state; a client
  parsing that email's content for a QR code must not assume it's always
  present.
- **No change** to the `ApprovalWorkflowRule` multi-step, per-visitor-
  category approval engine (`visitors/` — CRUD-only today) — this change
  uses only the company-wide `auto_approve_pre_registered_visitors` flag,
  per the reported scenario. Wiring the full rule engine into invitation
  approval is a separate, larger effort, flagged in design.md as a
  Non-Goal.
- **Tests**: `invitations/tests.py` needs cases for both status paths and
  the new approve endpoint (happy path, permission-denied, wrong-state
  409, tenant/branch isolation); `auth/tests.py` needs cases for the new
  resync endpoint.
