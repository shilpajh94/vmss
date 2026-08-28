## Context

See `proposal.md` - Why. Two independent threads, both scoped to test
coverage and dev tooling only:

1. `tests/test_workflow_full_lifecycle.py` (added by the already-archived
   `codebase-review-and-e2e-scenario-test` change) chains: platform login →
   tenant provisioning → admin login → bulk branch provisioning (Branch A)
   → Branch B built entity-by-entity → role management (custom role,
   permission catalog, grant/revoke, standard role) → staff invitation +
   approval → device-key provisioning → kiosk lookups (departments/options/
   hosts) → walk-in registration → branch-scoped invitation listing →
   reports rollup → branch-deletion guard. It never calls `GET /tenants/me`,
   never touches `visitor-categories`/`approval-workflow-rules`, and never
   calls `identity-verification`'s OTP endpoints.
2. `scripts/seed_dev_data.py` seeds one tenant, one branch (hardcoded
   `DEFAULT_BRANCH_CODE = "MAIN"`), the role catalog, and one admin user —
   idempotent, safe to re-run, but not enough sample data to click through
   every one of the 10 stages manually, and the branch-code constant is a
   second, driftable copy of `settings.registration_default_branch_code`.
3. **Discovered during `tasks.md` Section 3's implementation, not known at
   proposal time**: `scripts/seed_demo_workflow.py` already exists and
   already does almost everything a new "seed realistic data across all 10
   stages" script would do — real HTTP calls (not in-process shortcuts) that
   build org structure, a visitor category + approval workflow rule,
   several invitations, OTP requests, and a walk-in registration, tagged
   per-run and safe to re-run repeatedly. It does not provision a tenant
   itself (explicitly, to avoid "a second, divergent bootstrap path" — its
   own docstring), relying on `seed_dev_data.py` for that. Neither script
   has a reset/clear capability.

## Goals / Non-Goals

**Goals:**
- All 10 stages from the user's screenshot are exercised inside one
  continuous, real-HTTP test session, using each stage's actual request/
  response contract (no shortcut fixtures for something a real client
  would have had to call an endpoint to get — the existing file's own
  convention).
- `scripts/seed_dev_data.py`'s branch code is config-driven, not a second
  hardcoded copy.
- A new script can populate a local/dev database with realistic data
  spanning all 10 stages for manual exploration (Swagger, Postman, the
  actual web/app clients), and can optionally reset first — gated so it
  can never run destructively against a production-looking environment.

**Non-Goals:**
- Not wiring `identity_verification`'s proof token into invitation/walk-in
  creation, and not building approval-workflow-rule *evaluation* against
  invitations — both are explicitly out of scope, tracked separately, per
  `docs/features/registrations.md`/`docs/features/invitations.md`'s own
  "Not yet built" sections. This change only proves the existing, standalone
  endpoints for each work inside the same session as everything else.
- Not reordering any existing step in `test_workflow_full_lifecycle.py` —
  only inserting new steps at clearly-scoped points, so every existing
  variable/assertion in the file is untouched and the diff stays reviewable
  as pure addition.
- Not performing any database reset/seed action as part of this planning
  change — this is `design.md` for a script `tasks.md` will implement next;
  no table is truncated by writing this document.

## Decisions

**Insert, don't reorder.** The three new steps go at the nearest point in
the existing flow where their prerequisites already exist, not necessarily
in the screenshot's exact numeric order:
- `GET /tenants/me` right after `admin_login`, before bulk provisioning —
  the earliest point an access token exists (stage 02).
- Visitor category + approval workflow rule creation right after the role
  section's `re_grant_response` (reusing the just-fetched `reception_role_id`
  as the rule's `approverRoleId`, so no new role has to be created) and
  before the invitation section (stage 04, ahead of stage 05 — matches the
  screenshot's order and needs nothing invitations-related yet).
- OTP request + verify for `"walk.in.visitor@example.com"` (the walk-in
  payload's own primary-contact email, built by the existing
  `_invitation_payload("Walk In Visitor")` helper) right after the kiosk
  lookups (`hosts_response`) and immediately before the `walk_in_response`
  POST — narratively "the visitor verifies their contact, then walks in,"
  even though the walk-in endpoint itself doesn't check the token (Non-Goals
  above). This keeps kiosk-lookups-before-walk-in-submission, the existing
  file's already-correct chronology, intact; the screenshot's own 06/07
  ordering is a capability listing, not a call-order requirement, since a
  real kiosk always fetches its dropdowns before submitting the form they
  populate.

**`scripts/seed_dev_data.py`'s fix is a one-line read, not a rename.**
Replace `DEFAULT_BRANCH_CODE = "MAIN"` module constant with a direct read of
`settings.registration_default_branch_code` at the point the `Branch(...)`
row is constructed. No parameter is added and no caller changes — this
removes the second, driftable copy without touching the script's public
shape.

**No new seeding script — `scripts/reset_dev_tenant_data.py` does reset
only, nothing else.** Since `seed_demo_workflow.py` (plus `seed_dev_data.py`
for the tenant/branch/admin bootstrap it deliberately doesn't repeat) already
covers the seeding side end to end, the only real gap is a reset step. This
keeps single-responsibility clean: one script clears, two already-existing
scripts (re-)populate, run in sequence
(`seed_dev_data.py` → `seed_demo_workflow.py`) exactly like a first-time
setup already does — a reset environment and a brand-new environment
converge on the identical bootstrap path, not a second, divergent one.

Alternative considered (this proposal's original plan, before this
discovery): a combined `reset_and_seed_dev_data.py` that both clears and
re-seeds. Rejected once `seed_demo_workflow.py` was found — it would
duplicate that script's org-structure/category/invitation/OTP/walk-in
creation logic in a second place, which is exactly the "second, divergent
bootstrap path" `seed_demo_workflow.py`'s own docstring already rejects for
tenant provisioning. Reset-only keeps the addition to exactly the missing
piece.

**Reset clears rows, not the schema — `TRUNCATE` every table in the one
tenant's schema (except `alembic_version`), plus the global-schema rows
that reference it.** Concretely: every table in
`{settings.tenant_schema_prefix}{settings.default_tenant_slug}`'s schema
via `TRUNCATE ... CASCADE`, then `DELETE` the matching rows in
`global.tenant_user_index`, `global.registration_device_keys`, and
`global.platform_audit_events` (all four discovered as real FK constraints
into `global.tenants` while resolving this exact blocker earlier in this
apply session, resolving task 1.2's blocker). The `tenants` registry row and
the schema's own migration state are left untouched, so
`seed_dev_data.py`'s "tenant already exists" branch still runs its
re-sync-roles path correctly, and — because `tenant_user_index` was
cleared — its `already_indexed` check now correctly falls through to
recreate the branch and admin user fresh, giving a genuinely clean slate
without a schema drop/recreate/re-migrate round trip.

Alternative considered: drop and recreate the tenant's entire Postgres
schema. Rejected as unnecessarily destructive for what's actually needed
(fresh *rows*, not a fresh *schema* — the schema's own migrations don't
need re-running) and slower to iterate with than a table-scoped clear —
confirmed firsthand earlier in this same apply session, where exactly this
recovery was needed for an unrelated, pre-existing migration-history
mismatch and took a full re-migration run.

**Reset is gated by environment and requires explicit confirmation — never
a silent default.** `scripts/reset_dev_tenant_data.py`:
1. Refuses outright (prints an error, exits non-zero, touches nothing) when
   `settings.environment.lower() == "production"` — the same posture
   `main.py::_docs_urls` already applies to Swagger availability, applied
   here to a strictly more dangerous action.
2. Prints exactly which tenant/schema is about to be cleared and exits
   without doing anything unless invoked with `--yes` (or a fresh
   interactive confirmation) — there is no partial/no-op mode to fall back
   to the way `seed_dev_data.py`/`seed_demo_workflow.py` have one; this
   script only ever does one destructive thing, so it must never run by
   accident.
3. Only ever touches the one tenant resolved from
   `settings.default_tenant_slug` — never a cross-schema or cross-tenant
   operation, so a second, real tenant's data in the same physical database
   is never touched.

## Risks / Trade-offs

- [A developer runs `reset_dev_tenant_data.py` against a shared dev database
  another developer or the web/app team is actively using] → Mitigated by
  scoping the clear to one named tenant schema only (never cross-tenant)
  and by the script printing exactly what it's about to clear and requiring
  explicit `--yes` confirmation every time — no persistent "always reset"
  config to forget is left set.
- [Inserting three new steps into an already-large, 500+-line test file
  makes it harder to read] → Mitigated by keeping each insertion small and
  labeled with the same `# --- <section> ---` comment convention the file
  already uses, and by not touching any existing step's code or assertions.
- [The OTP round trip adds a real dispatch call] → The existing file
  already fakes `tasks.send_approval_notification.delay`/
  `send_tracking_notification.delay`; the OTP step needs the same treatment
  for `identity_verification.senders.email_sender` (per
  `identity_verification/tests.py`'s own `_RecordingSender` pattern) so
  this test doesn't depend on a real SMTP catcher being reachable.

## Migration Plan

1. Fix `scripts/seed_dev_data.py`'s hardcoded branch code.
2. Add the three new steps to `tests/test_workflow_full_lifecycle.py`.
3. Add `scripts/reset_dev_tenant_data.py` (reset only) with the
   environment guard and explicit-confirmation requirement.
4. Document the reset script, and the
   `reset_dev_tenant_data.py` → `seed_dev_data.py` → `seed_demo_workflow.py`
   sequence for a fully fresh dev dataset, next to the existing
   "Provisioning the default tenant/branch" section in
   `docs/features/configuration.md`.
5. No rollback concern: steps 1-2 are pure test/tooling additions with no
   production code path affected; step 3 is a new, never-auto-invoked
   script.
