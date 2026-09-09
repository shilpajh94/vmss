## Context

Small, focused change unblocking the companion `VMMS_WEB` change
`role-based-invitation-workflow`. See `proposal.md` for the full "why."

`Invitation.department_to_visit` is currently `Mapped[str]` (non-nullable)
in `models.py`, backing the `VisitDetailsSubmit.department_to_visit: str`
field this change relaxes. Every existing row already has a non-null value
— this is a pure constraint-loosening, not a backfill or data-migration
concern.

## Goals / Non-Goals

**Goals:**
- Make `department_to_visit` genuinely optional end-to-end: request schema,
  model/column, response schemas, and every render site (email templates,
  approval-email visit-detail section) that currently assumes a non-null
  string.
- Keep this a strictly additive, non-breaking API change — no existing
  caller that always supplies `departmentToVisit` sees any difference.

**Non-Goals:**
- Not adding a UI or endpoint for reception to bulk-fill missing
  departments — the existing `PATCH /invitations/{id}/edit` endpoint
  already covers filling it in per-invitation, one at a time.
- Not touching `purposeOfVisit`/`expectedDuration`, which stay required —
  only `departmentToVisit` is in scope, per the companion web change's
  actual need.

## Decisions

### D1: Nullable column via a new Alembic tenant migration, not a data backfill
`ALTER COLUMN department_to_visit DROP NOT NULL` on the existing column —
every current row already has a value, so there's nothing to backfill.
Follows the same `alembic_tenant/versions/` pattern as every other
tenant-schema migration in this repo (`database-architecture.md` §5),
applied once per tenant schema the same way `b4f7a1c9d2e6` (the
`role-based-invitation-workflow` change's own migration) was.

### D2: Render sites treat null the same way they already treat a resolved-vs-unresolved host
The approval email's visit-detail section, and any other place that
interpolates `department_to_visit` into user-facing text, render a neutral
placeholder ("Not yet assigned") when null, mirroring the existing
resolved-host-vs-front-desk-fallback pattern
(`docs/features/invitations.md`'s "Approval Notification Email Includes
Full Visit and Host Detail") rather than an empty string or a template
rendering error.

## Risks / Trade-offs

- **[Risk]** A render site is missed and either raises on `None` or renders
  the literal string `"None"`. → **Mitigation**: task list requires a
  grep-driven audit of every `department_to_visit`/`departmentToVisit`
  read site (schemas, templates, tasks.py) before considering the change
  done, not just the obvious approval-email path.
- **[Trade-off]** Some invitations will now genuinely have no department at
  all until reception edits them in — accepted, since that's the entire
  point of the companion web change (visitors/staff no longer guess it at
  creation).

## Migration Plan

Apply the new tenant migration to the dev tenant schema
(`alembic_tenant.ini -x tenant_schema=tenant_default upgrade head`) the same
way `role-based-invitation-workflow`'s migration was applied. No data
migration, no rollback complexity beyond a normal `downgrade` re-adding
`NOT NULL` (safe only if no null rows exist at that point — flag this in
the migration's own downgrade docstring rather than silently allowing a
downgrade that would fail on real data).
