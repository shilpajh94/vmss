# Visitor Types

Covers API-05 (Visitor Category CRUD with a configurable form schema) and
API-06 (approval workflow rules per category). Both tables are tenant-scoped
by schema (`Base`, not `GlobalBase`) and tenant-wide — not branch-scoped, same
posture as `org_structure`'s `Company`/`Branch` CRUD
(`docs/features/org_structure.md`).

Lives in `visitors/` per `project-rules.md`'s directory-structure note
("visitor master data, visitor types, blacklist, watchlist"). Visitor master
data, blacklist, and watchlist are not built yet.

## VisitorCategory

A configurable visitor type (e.g. "Vendor", "Interview Candidate",
"Contractor", "Guest"). `formSchema` is a JSON list of field definitions
describing what a pre-registration/check-in form for this category collects
beyond the fixed visitor fields (name, phone, photo, etc. — owned by the
not-yet-built visitor-master-data feature). Each field definition is:

```json
{
  "name": "company_name",
  "label": "Company Name",
  "fieldType": "text",
  "required": true,
  "options": null,
  "helpText": null
}
```

`fieldType` is one of `text`, `textarea`, `number`, `date`, `select`,
`checkbox`, `email`, `phone`. `name` is validated as a snake_case identifier
(`^[a-z][a-z0-9_]*$`) — it's the key visitor-submitted form data will be keyed
by once `invitations`/`checkin` are built — and must be unique within one
category's schema (validated at the API boundary, `security-architecture.md`
§4, not left to a DB constraint on a JSONB column). A `select`-type field
must declare a non-empty `options` list — `checkbox` has no such requirement
(it's a single boolean toggle here, not a multi-select group).

Whether a category requires approval is **not** a column on this table — it's
purely a function of whether it has any `ApprovalWorkflowRule` rows. Zero
rows means walk-in/pre-approved.

`VisitorCategory.name` and `.code` are each backed by a **partial** unique
index scoped to `deleted_at IS NULL`, not an unconditional one, so a
soft-deleted category's name/code is freed for reuse — same fix and
rationale as `docs/features/org_structure.md`'s "Soft-deleted rows free
their code/number for reuse" section.

### Badge, NDA, escort, and duration fields

A design-vs-implementation review of the admin portal's visitor-categories
screen (`openspec/changes/add-role-management-and-org-field-gaps/`) added
four fields, all optional:

- `badgeColor` — a free-form color value (e.g. a hex string) for the
  category's badge swatch in the admin UI.
- `ndaRequirement` — one of `digital`, `signed_pdf`, `optional`, `none`.
- `escortRequirement` — one of `self_escort`, `access_logs_only`,
  `always_required`, `gate_check_in_only`.
- `maxDurationMinutes` — the category's maximum visit duration, in minutes.

Both enum fields are validated at the API boundary (422 on an unrecognized
value) the same way `fieldType`/`gateType` elsewhere in this codebase are —
plain strings in the database, an `Enum` at the Pydantic layer.

## ApprovalWorkflowRule

One ordered step (`stepOrder`, starting at 1) in a category's approval chain:
the approver at that step is whoever holds `approverRoleId`
(`auth.models.Role`). `isMandatory` marks whether the step can be skipped;
`escalationMinutes`/`autoApproveMinutes` are optional timers for a future
notification/escalation job. `(visitorCategoryId, stepOrder)` is unique among
non-deleted rows — no two active rules can claim the same slot in one
category's chain, but a soft-deleted rule's slot is freed for reuse (same
partial-unique-index fix as `VisitorCategory` above).

This is configuration only. Evaluating these rules against an actual visit
request — snapshotting them onto a submitted invitation, sequencing step
approval/rejection, escalating, auto-approving — is the `approvals`
feature's job (`project-rules.md`'s "configurable approval workflow
engine"), the same way `org_structure`'s tables describe the org chart
without owning check-in behavior themselves. See
`docs/features/approvals.md` for how a category's rules actually take
effect once `invitations` submits against them.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/visitor-categories` | `visitor-categories:manage` | Create a category. 409s on duplicate `name`/`code`. |
| GET | `/api/v1/visitor-categories` | `visitor-categories:view` | Paginated, sortable (`name`/`created_at`) list. |
| GET | `/api/v1/visitor-categories/{id}` | `visitor-categories:view` | Fetch one category. |
| PUT | `/api/v1/visitor-categories/{id}` | `visitor-categories:manage` | Update a category (partial). |
| DELETE | `/api/v1/visitor-categories/{id}` | `visitor-categories:manage` | Soft-delete a category. |
| POST | `/api/v1/approval-workflow-rules` | `approval-workflow-rules:manage` | Create a rule; 404s if `visitorCategoryId`/`approverRoleId` don't resolve, 409s on a duplicate `(category, stepOrder)`. |
| GET | `/api/v1/approval-workflow-rules` | `approval-workflow-rules:view` | Paginated, sortable (`step_order`/`created_at`) list, optionally narrowed by `visitorCategoryId`. |
| GET | `/api/v1/approval-workflow-rules/{id}` | `approval-workflow-rules:view` | Fetch one rule. |
| PUT | `/api/v1/approval-workflow-rules/{id}` | `approval-workflow-rules:manage` | Update a rule (partial). |
| DELETE | `/api/v1/approval-workflow-rules/{id}` | `approval-workflow-rules:manage` | Soft-delete a rule. |

Every create/update/delete above queues an `AuditLog` write
(`auth/audit.py::record_audit_log`) as a `BackgroundTasks` task, per
`security-architecture.md` §5.

## Permissions

`visitor-categories:view`/`:manage` and `approval-workflow-rules:view`/`:manage`
are seeded by `auth/rbac_catalog.py`. `reception` and `host` get
`visitor-categories:view` by default (they need to know what categories exist
to check a visitor in or raise an invitation); workflow-rule configuration is
`admin`-only in the default seed.
