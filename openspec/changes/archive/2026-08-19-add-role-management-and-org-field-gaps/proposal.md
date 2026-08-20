## Why

The web and app teams cross-checked the implemented API against the actual admin, staff, and kiosk screen designs (`Requirements/VMS admin/`, `Requirements/staff VMS/`, `Requirements/VMS Kiosk/`) and found real gaps. The most significant: there is **no Role management API at all** — only a fixed five-role seed catalog (`auth/rbac_catalog.py`) and an endpoint to assign an *existing* role to a user (`POST /auth/users/{id}/branch-roles`). The admin design's employee list shows role badges ("Security Admin", "System Admin") that don't exist in the seeded catalog, confirming tenants need to define their own roles, not just use the five defaults. Beyond that, several existing schemas are missing fields the designs require (Branch, Building, Floor, Department, ReceptionDesk, SecurityGate, VisitorCategory, Company, Employee), and one existing hierarchy (Department) is modeled against the wrong parent.

Three larger, genuinely new subsystems also surfaced during this review — check-in/checkout, staff SSO login, and a dynamic form-builder — but these are net-new features, not missing fields on what's built. They are called out under **Not in Scope** below for separate future changes, so this change stays focused and reviewable.

## What Changes

- Add full Role management: create, list, get, update, and delete/deactivate a tenant-defined role with its permission set — filling the gap the five-role-only seed catalog left open.
- Add a role-name-uniqueness "verify" pre-check endpoint (`GET /auth/roles/verify?name=...`), mirroring the existing `get_by_code`/`get_by_name` pre-check pattern already used for Branch/Building/VisitorCategory.
- Add a branch-role revocation endpoint (`DELETE /auth/users/{id}/branch-roles/{assignmentId}`) — grant existed with no corresponding revoke.
- **BREAKING (spec only, not wire-compatible with the old assumption)**: revise the "exactly five standard roles" requirement in the `auth` capability to "at least the five standard roles, plus zero or more tenant-defined custom roles" — the five seeded roles remain non-deletable and non-renameable, but a tenant may now create additional roles.
- Add `avatar_url` and a resolved `branch_roles` list to `EmployeeOut` so the admin employee directory can render photo and role/access columns.
- Add missing fields to `org-structure` entities per the admin designs:
  - `Branch`: `city`, `country`, `contact_person_user_id`, `contact_email`, `contact_phone`, `operating_hours_from`, `operating_hours_to`, `notes`; allow `is_active` to be set at creation.
  - `Building`: allow `is_active` to be set at creation.
  - `Floor`: `capacity`, `capacity_type` (guests/staff), `access_level` (public/restricted/secure).
  - `Department`: add `branch_id` (direct FK, `floor_id` becomes optional) so a department can be created and listed by branch without requiring a floor step, per the design's creation flow; add `head_of_department_user_id`, `description`.
  - `ReceptionDesk`: replace boolean `is_active` with a tri-state `status` (`active`/`maintenance`/`inactive`); add `assigned_receptionist_user_id`, `operating_hours_from`, `operating_hours_to`.
  - `SecurityGate`: replace boolean `is_active` with a tri-state `connectivity_status` (`online`/`maintenance`/`offline`); add `high_security` flag (the design's 4th gate type, "High Security", layered on top of the existing entry/exit/both `gate_type`); add `auth_method`.
  - `Company`: add `default_timezone`, `auto_approve_pre_registered_visitors`, `badge_expiry_duration_minutes` (the "Organisation Configs" screen's policy fields).
- Add missing fields to `visitors` capability's `VisitorCategory`: `badge_color`, `nda_requirement` (enum: `digital`/`signed_pdf`/`optional`/`none`), `escort_requirement` (enum: `self_escort`/`access_logs_only`/`always_required`/`gate_check_in_only`), `max_duration_minutes`.

## Not in Scope (flagged for separate future changes)

- **Check-in/checkout feature** — no `checkin` package exists; the staff visitor-dashboard, host-audit-trail stats, and visitor-pass dashboard designs all depend on check-in state that has no backing table today. Needs its own change.
- **Staff SSO login** — `staff-sso-login.pdf` shows an SSO-only login screen; no SAML/OIDC code exists anywhere in `auth/`. Protocol choice (SAML vs OIDC) is a product/infra decision, not something to assume here.
- **Dynamic form-builder** — `form-builder-*.pdf` describe a stepped, draft/publish, 13-field-type form builder scoped per branch workspace; the existing `VisitorCategory.form_schema` is a flat, always-live, 8-field-type list. This is a net-new feature, not a field gap.
- **Workflow-builder person-based approvers** — the design's "Add Workflow" screen picks a named individual per approval level; `ApprovalWorkflowRule.approver_role_id` only supports role-based routing. Whether to add an `approver_user_id` alternative (or replace role routing entirely) needs a product decision the single captured screen doesn't resolve.
- **Audit-trail read API** — `host-audit-trail.pdf` needs a `GET /audit-logs` endpoint with pagination/filters and a new `audit-logs:view` permission; `AuditLog` today is write-only from the application's side. Also needs visitor-name/zone/method resolution that depends on the check-in feature above.
- **Invitations dashboard (list/approve/deny)** — `visitor-dashboard.pdf`'s Kanban view needs `GET /invitations` (list/filter/paginate) plus approve/deny state transitions; `Invitation.status` is currently a write-once `"submitted"` string with no state machine, and the already-seeded `invitations:view`/`invitations:cancel` permissions have no endpoints using them yet.
- **Visitor kiosk portal update/OTP/device-identity questions** — `visitor-portal-landing.pdf` implies an update-after-submit action with no PATCH endpoint; the request form implies an OTP step already tracked as a known gap in `docs/features/registrations.md`; and how a public web kiosk (vs. a provisioned physical device) obtains a device key for `POST /registrations/walk-in` is unresolved. None of these touch role management or the org-structure/visitors field gaps this change addresses.

## Capabilities

### Modified Capabilities
- `auth`: adds Role CRUD (create/list/get/update/delete) and a name-uniqueness verify check, adds branch-role revocation, revises the "exactly five standard roles" requirement to allow tenant-defined custom roles alongside the five non-deletable seeded ones, and extends the Employee Directory Sync requirement's read side with avatar/role-badge fields.
- `org-structure`: adds fields to `Branch`, `Building`, `Floor`, `Department` (plus a `branch_id` FK), `ReceptionDesk`, `SecurityGate`, and `Company` per the admin design screens; replaces `ReceptionDesk`/`SecurityGate` boolean status with tri-state status fields.
- `visitors`: adds `badge_color`, `nda_requirement`, `escort_requirement`, and `max_duration_minutes` to `VisitorCategory`.

## Impact

- **Code**: `src/vmss_api/auth/{models,schemas,router,service,repository,rbac_catalog}.py`, `src/vmss_api/org_structure/{models,schemas,router,service}.py`, `src/vmss_api/visitors/{models,schemas,router,service}.py`.
- **Migrations**: new `alembic_tenant/versions/` migration(s) for the new/changed columns on `roles` (none needed — `Role` already has no new columns, only new endpoints), `branches`, `buildings`, `floors`, `departments`, `reception_desks`, `security_gates`, `companies`, `visitor_categories`. Existing tri-state conversions (`ReceptionDesk.is_active` → `status`, `SecurityGate.is_active` → `connectivity_status`) need a data-preserving column migration (`true` → `active`/`online`, `false` → `inactive`/`offline`).
- **RBAC catalog**: `auth/rbac_catalog.py` gains `roles:manage`/`roles:view` permission codes.
- **Docs**: `docs/features/auth.md` (if present) or a new one, plus `docs/features/org_structure.md`/`docs/features/visitors.md` updates per `project-rules.md`'s "new/changed endpoint needs a docs update" rule.
- **Tests**: new permission-denied and tenant-isolation cases for role CRUD per `testing-standards.md` §2; updated factories for every changed model.
