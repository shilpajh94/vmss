## Context

- `access_control/repository.py::ZoneMappingRepository.effective_zone_ids(invitation_id, category_id)` returns the invitation's own zones, else the category defaults, else an empty set. Two callers: `access_control/service.py` (gate scan) and `access_control/checkin_gate.py` (front-desk check-in). `can_enter` is pure and takes `allowed_zone_ids`.
- `Zone` is branch-scoped, soft-deletable, has `is_active`; the unique code index is partial on `deleted_at IS NULL`.
- Tenant tables live in `alembic_tenant/`.

## Goals / Non-Goals

**Goals:** a forgotten zone assignment never blocks a visitor from the branch's default zone; one resolver change covers every entry path; admin can set/clear the default.

**Non-Goals:** per-category default zones, relaxing any other `can_enter` check, backfilling data.

## Decisions

**1. Column, not a setting.** `zones.is_default boolean not null default false`, plus partial unique index `uq_zone_branch_default` on `(branch_id) WHERE is_default AND deleted_at IS NULL`. Chosen over a `branches.default_zone_id` FK because it needs no cross-table cycle, and the index makes "one default per branch" a database guarantee rather than service discipline. The index is the backstop; the service clears the old default first.

**2. Resolver gains the branch.** `effective_zone_ids(invitation_id, category_id, branch_id)` returns `explicit_or_category | {default_zone_id}`. The default is read with one query (`SELECT id FROM zones WHERE branch_id = :b AND is_default AND is_active AND deleted_at IS NULL`), so at most three queries, independent of zone count (`query-performance.md`). Union semantics: reception can still narrow to a subset of non-default zones, but the default is always present. `can_enter` is untouched; an inactive/deleted default is simply not added (and would fail `zone_inactive` anyway).

**3. Setting the default.** `ZoneCreate`/`ZoneUpdate` get `is_default: bool | None`. When true, the service in one transaction clears `is_default` on the branch's current default, then sets it on this zone; one audit entry with before/after (old and new default ids). Setting `false` on the current default just clears it. Requires `zones:manage` at the zone's branch, like every zone write.

**4. Protect the default.** Soft-deleting or setting `is_active=false` on a default zone returns 409 ("choose another default zone first"). Chosen over silently clearing the flag so an admin never loses the safety net without noticing. A zone must be active and live to be made default (422 otherwise).

**5. Read side.** `ZoneOut.is_default`; list filter `is_default: bool | None` (explicit typed param per `api-conventions.md`). `GET /invitations/{id}/zones` is unchanged: it reports the explicit assignment only, so `[]` still means "category defaults apply" and the default zone is implicit.

**6. Migration.** One tenant migration: add column with server default false, create the partial unique index; downgrade drops both. No grants needed (no new permission). Applies to fresh and existing tenant schemas.

**7. Layering and docs.** Router → service → repository; no new routes, so `_TAGS_METADATA` and `api.py` are unchanged; `tests/test_api_documentation.py` still runs because a response schema changed. Update `docs/features/access_control.md` (the "default deny" paragraph and the zone endpoint table).

## Risks / Trade-offs

- **Always-included default** means reception cannot exclude a visitor from the default zone. Mitigation: it should be a low-risk common area; documented. Blacklist/approval/time checks still deny.
- **Mis-set default** (e.g. server room) grants everyone access. Mitigation: audited with before/after; admin-only (`zones:manage`).
- **Default with no gate link** looks configured but denies with `gate_not_linked`. Documented; not enforced at set time since gate links are edited independently.
