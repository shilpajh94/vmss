## Context

`alembic_tenant/versions/c1d8e5f9a2b3_invitation_point_of_contact.py` and
`alembic_tenant/versions/afb2544db111_form_builder_steps_and_fields.py`
(→ `762e2a7cf5d1` → `f1a2c7e9b3d5`) both set
`down_revision = "6f3a1c9d4e7b"` — they were authored against the same
parent instead of one chaining after the other, so `alembic_tenant` has
two heads and no merge revision. `platform/service.py::upgrade_tenant_schema`
/ `upgrade_all_tenant_schemas` calls `command.upgrade(cfg, "head")` and
`get_tenant_migration_head` calls `ScriptDirectory.get_current_head()` —
both raise `CommandError: Multiple head revisions are present` while the
tree is in this state, so the normal existing-tenant upgrade path
(`tenant-schema-maintenance` spec) cannot run at all, and
`backend_pre_start.py::check_tenant_schema_drift` only logs a `WARNING`
regardless of cause. See proposal.md for the resulting production impact.

## Goals / Non-Goals

**Goals:**
- Restore a single, unambiguous `alembic_tenant` head that includes both
  the POC-fields and form-builder migrations.
- Get every existing tenant schema (`tenant_default` at minimum) onto
  that head, fixing the live `poc_user_id` error.
- Make a future branch-without-merge mistake fail loudly at CI time and,
  as a last resort, at startup — not surface as an unhandled 500 weeks
  later.

**Non-Goals:**
- Redesigning how tenant migrations are authored or reviewed beyond
  adding the one CI guard described here.
- Automatic self-healing (auto-generating a merge revision at runtime) —
  merges are authored and reviewed like any other migration, never
  machine-generated during deploy.

## Decisions

**Reconcile the branches with an Alembic merge revision, not a
`down_revision` rewrite.** Rewriting `f1a2c7e9b3d5`'s (or
`c1d8e5f9a2b3`'s) `down_revision` to chain after the other branch was
considered and rejected: different environments may already have applied
one branch but not the other (dev might have `f1a2c7e9b3d5` applied,
another env might have `c1d8e5f9a2b3` applied, neither in the same
order), and rewriting history changes what "applied" means for a
revision id that may already be recorded in some environment's
`alembic_version` table. A merge revision
(`alembic -c alembic_tenant.ini merge -m "merge poc and form-builder
heads" c1d8e5f9a2b3 f1a2c7e9b3d5`) is the standard Alembic mechanism for
this: it's a no-op schema change whose `down_revision` is the tuple of
both branch tips, so `upgrade head` correctly applies whichever of the
two branches a given environment is still missing, regardless of which
one it already has.

**Detect multiple heads via `ScriptDirectory.get_heads()`, not by
catching `CommandError`.** `get_heads()` returns the list of head
revision ids without raising, so `get_tenant_migration_head` (and the new
drift check) can distinguish "ambiguous tree" (`len(heads) > 1`) from any
other Alembic failure with an explicit, typed condition instead of
string-matching an exception message. `upgrade_all_tenant_schemas` and
`check_tenant_schema_drift` both call through this single check so the
"more than one head" condition is detected the same way everywhere,
rather than each call site handling a raw `CommandError` differently.

**Escalate the startup check from `WARNING` to `ERROR` only for the
multi-head case, per-tenant lag stays `WARNING`.** Ordinary drift (a
tenant a few revisions behind) is expected between a migration merging
and an ops run of `scripts/upgrade_all_tenants.py`, and `WARNING` is the
right severity per `logging-observability.md`'s level policy. An
ambiguous tree is a defect in the migration history itself — it blocks
*every* tenant from being upgradable, not just one — so it's logged at
`ERROR` (`security-architecture.md`/`logging-observability.md`'s bar for
"needs a human to look").

**Add an `alembic_tenant heads` CI guard rather than relying on the
startup check alone.** The startup check catches this in a running
environment; a CI guard catches it before merge, which is strictly
cheaper. `CI-CD/Azure-Pipeline-API-DEV.yml`'s `QualityTest`/`Scanning`
job currently has no steps at all (not even `pytest`), so this also
closes the pre-existing gap that let a multi-head migration merge
unnoticed in the first place.

## Risks / Trade-offs

- **[Risk]** Running `scripts/upgrade_all_tenants.py` touches every
  tenant schema in an environment in one pass. → Mitigation: only one
  tenant (`tenant_default`) exists today per `project-rules.md`, so
  blast radius is currently minimal; run it against staging first and
  confirm invitation creation succeeds before running against
  production.
- **[Risk]** The merge revision must not silently re-apply or conflict
  with schema objects either branch already created in a given
  environment. → Mitigation: merge revisions are no-op by construction
  (empty `upgrade()`/`downgrade()` bodies) — Alembic only uses it to
  unify the version graph, so there's no schema DDL to conflict.
- **[Risk]** Downgrading a tenant schema that has already taken real
  traffic on the merged head, if the merge revision turns out wrong.
  → Mitigation: prefer a forward-fix migration over `alembic downgrade`
  against a live tenant schema, consistent with the project's
  soft-delete/no-destructive-ops posture (`database-architecture.md`
  §4).

## Migration Plan

1. Author the merge revision; verify locally that
   `alembic -c alembic_tenant.ini heads` reports exactly one head.
2. Harden `get_tenant_migration_head`, `upgrade_all_tenant_schemas`, and
   `check_tenant_schema_drift` for the multi-head condition (`Decisions`
   above).
3. Add the CI guard step.
4. Deploy the merge migration and hardened code.
5. Run `scripts/upgrade_all_tenants.py` against staging, confirm the
   `poc_user_id` columns exist and invitation creation succeeds, then run
   it against production.
6. Confirm `tenant_schema_versions` reflects the merged head for every
   tenant and the original repro (submit an invitation) no longer 500s.

## Open Questions

- Which environments beyond the one reproducing this (dev/staging/prod)
  currently have a tenant schema below head, and in what order should
  `scripts/upgrade_all_tenants.py` be run across them? Confirm with
  whoever owns deploys before executing step 5 in each environment —
  doesn't change the approach or task breakdown above.
