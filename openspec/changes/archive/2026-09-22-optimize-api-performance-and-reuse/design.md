## Context

See `proposal.md` - Why / What Changes for the full list and motivation.
All nine items were found by a full read-through of `src/vmss_api/*` against
`query-performance.md`, `database-architecture.md` §3, and
`fastapi-architecture.md` §2 (layering). The codebase already follows the
hard rules correctly almost everywhere (no repository builds its own
engine, `TenantScopedRepository.paginate` is genuinely shared, `invitations`
uses `lazy="raise"` to fail loudly instead of silently N+1-ing) — this
design covers the residual, narrow set of exceptions, not a rearchitecture.

Three of the nine items are duplicated helpers whose own docstrings
name the sibling copy they mirror (`identity_verification/router.py`'s
idempotency helpers say they mirror `invitations/router.py`'s;
`dashboard`/`invitations`/`org_structure`'s `_branch_filter` cross-reference
each other). That's a strong signal the extraction target is already
obvious to whoever wrote the copies — this design just names the one
place each should live.

## Goals / Non-Goals

**Goals:**
- Every fix is verified behavior-preserving: same response body shape,
  same status codes, same side effects, same ordering, for every existing
  test and for the manual smoke check in the Migration Plan.
- Each of the nine items lands as an independent, revertible unit — no
  item depends on another being merged first, so a regression can be
  bisected to one specific change.
- Shared helpers go in `core/` only when 2+ features already duplicate
  the logic today (matches `fastapi-architecture.md` §6's "core doesn't
  depend on features" boundary — none of the extracted helpers need to
  import from a feature package).

**Non-Goals:**
- No new caching layer, no new database indexes, no schema/migration
  changes — everything here is query-shape and code-location only.
- No change to `sync_employee_directory`'s per-row `flush()` in
  `auth/service.py::create_user` (audit found this but the per-row flush
  is intentional — it lets a duplicate-key `IntegrityError` be attributed
  to the specific offending employee row during a bulk sync). Flagged as
  a follow-up candidate, not part of this change: fixing it needs a
  bulk-insert-with-per-row-conflict-attribution strategy (e.g. a bulk
  existence pre-check plus `add_all`) that's a bigger design question on
  its own and risks masking which row failed if done carelessly.
- No test-suite restructuring. Existing `tests.py` files gain targeted
  new cases (see Migration Plan) but keep their current structure.

## Decisions

**1. `form_builder/service.py::list_fields_for_steps`** — replace the
per-step loop with `select(FormField).where(FormField.step_id.in_(step_ids))`,
then group results into a `dict[UUID, list[FormField]]` in Python
(`itertools.groupby` needs a sort first; a plain loop appending to
`defaultdict(list)` is simpler and the result set is small). Preserves the
existing per-step ordering by sorting each group by `FormField.position`
exactly as the old per-step query did.

**2. `visitors/service.py::bulk_create_visitor_categories`** — two
pre-fetch queries (`WHERE code IN (...)`, `WHERE name IN (...)`) before the
loop, building `set[str]` lookups for the loop's existing duplicate-check
logic. The loop body's decision logic (skip vs. create, error accumulation
per name) is unchanged — only the exists-check source changes from a
query to a set-membership test. The post-commit per-row `refresh()` loop
is replaced with one `select(VisitorCategory).where(id.in_(created_ids))`
re-query; response construction maps over the re-queried rows in the same
input order as before (preserved via a dict keyed by id, iterated in the
original `created_ids` order) so client-visible ordering doesn't change.

**3. `org_structure/service.py::provision_branch`** — reduce per-row
flush to per-level flush: `add()` the branch and flush once, `add_all()`
every `Building` and flush once, `add_all()` every `Floor` and flush once.
Alternative considered: add real ORM `relationship()`s between
`Branch`/`Building`/`Floor` and let SQLAlchemy's unit-of-work sort the
flush order automatically, removing manual flushes entirely. Rejected for
this change — it touches `models.py` relationship configuration used
elsewhere (cascade behavior, lazy-loading defaults) and is a larger,
separately-reviewable change; per-level batching gets the same
round-trip reduction (N+M+1 → 3) without touching the model layer.

**4. Idempotency cache extraction** — new `core/idempotency.py` exposing
`cached_response(redis, tenant_id, namespace, key) -> Envelope | None` and
`cache_response(redis, tenant_id, namespace, key, envelope, ttl_seconds)`,
parameterized by `namespace` (`"invitations"`, `"audit-trail"`,
`"identity-verification"`) so the Redis key shape
(`vmss:{tenant_id}:{feature}:idempotency:{key}`, per
`database-architecture.md` §6) is unchanged for every existing cached
entry — this matters because it means in-flight/cached idempotency keys
from before the deploy remain valid after it (no cache-key migration).
`invitations/router.py`, `audit_trail/router.py`, and
`identity_verification/router.py` each replace their local
`_idempotency_cache_key`/`_cached_response`/`_cache_response` with calls
into this module.

**5. `_branch_filter` extraction** — one function in `core/tenancy.py`
(next to the existing `BranchScope` type, since branch-scope resolution
is already cross-cutting infra there per `fastapi-architecture.md` §6):
`branch_filter(column: InstrumentedAttribute, branch_scope: BranchScope)
-> ColumnElement | None`, returning `None` for `"all"` and `column.in_(...)`
otherwise — exactly `org_structure`'s existing version, since it's already
parameterized correctly. `dashboard/repository.py` and
`invitations/repository.py` switch their local copies to call this.

**6. Image content-type validation extraction** — `validate_image_only(
content: bytes, max_size: int, field_label: str) -> None` added to
`core/storage.py` next to the existing `_ALLOWED_CONTENT_TYPES` sniff logic
it wraps; raises the same `422` shape each call site raises today, with
`field_label` (`"avatar"` / `"photo"`) substituted into the existing error
message so the client-visible error text is byte-identical to today's.
`auth/service.py::upload_avatar` and `invitations/service.py::_validate_photo`
call it instead of hand-rolling the `{"image/jpeg", "image/png"}` check.

**7. `approvals/service.py::_user_holds_role_at_branch` layering fix** —
move the `select(UserBranchRole.id)...` statement into
`auth/repository.py::UserBranchRoleRepository.holds_role_at_branch(user_id,
role_id, branch_id) -> bool`, matching the existing method style on that
repository. `approvals/service.py` calls the repository method through the
`UserBranchRoleRepository` instance it's already given (checked: the
service already receives a `UserBranchRoleRepository` for other calls, so
this isn't a new constructor dependency).

**8. `paginate_with_joins` on `TenantScopedRepository`** — a new method
alongside the existing `paginate` in `core/database.py`, accepting an
`extra_joins: Sequence[tuple[Any, Any]]` (target, onclause) applied via
`.join()` before the count and page queries, otherwise identical to
`paginate`'s existing count+limit+offset shape. `FloorRepository.list_page`
and `ReceptionDeskRepository.list_page` switch to it, passing their
existing join targets; the SQL each produces should be equivalent to what
they hand-roll today (verified by comparing `str(stmt)` in a throwaway
script during implementation, not shipped as a test).

## Risks / Trade-offs

- [Batched `IN (...)` query changes result ordering vs. N sequential
  single-row queries, which could silently change list order in a
  response] → Every affected read path (`list_fields_for_steps`, the
  bulk-create re-query) explicitly re-sorts in Python to the
  previously-observed order (by `position` or by input order) rather than
  relying on the database's incidental ordering — called out per-decision
  above, and pinned down by a new ordering assertion in each item's test.
- [`core/idempotency.py` becoming a second place idempotency logic can
  drift, if a future feature copies instead of importing it] → Not fully
  preventable by this change alone; mitigated by making the new module's
  docstring explicit ("import this, do not copy") and by
  `git grep _idempotency_cache_key` returning zero feature-local hits
  after this change, so a future copy is a visible regression in review.
- [`provision_branch`'s flush-count reduction could reorder which
  `IntegrityError` (e.g. a duplicate building code) surfaces first if two
  buildings conflict] → Existing tests for `provision_branch` cover the
  single-conflict case, not multi-conflict ordering; this is a pre-existing
  gap the change doesn't need to fix, but the task list adds a regression
  test pinning current single-conflict error behavior before touching the
  flush structure, so a behavior change here is caught even though
  multi-conflict ordering itself stays unspecified.
- [Moving `_user_holds_role_at_branch`'s query into a repository method
  used only by `approvals` could look like dead-code duplication if a
  reviewer doesn't check `approvals` is the only caller] → Named
  `holds_role_at_branch` generically (not `approvals_holds_role_at_branch`)
  so a second caller can reuse it without another layering violation.

## Migration Plan

No deployment/rollback complexity beyond normal code deploy — no schema
migration, no data backfill, no feature flag needed (every change is
behind an existing interface with unchanged inputs/outputs). Land as nine
independent commits/PRs in this order, running `ddev exec uv run pytest`
after each and confirming the touched feature's `tests.py` plus the full
suite stays green before moving to the next:

1. Extract `core/idempotency.py`, switch the three routers over (lowest
   risk — pure code motion, no query-shape change).
2. Extract `_branch_filter` into `core/tenancy.py`, switch the three
   repositories over (same: pure code motion).
3. Extract `validate_image_only` into `core/storage.py`, switch
   `auth`/`invitations` over.
4. Move `_user_holds_role_at_branch` into `auth/repository.py`.
5. Batch `form_builder/service.py::list_fields_for_steps`.
6. Batch `visitors/service.py::bulk_create_visitor_categories`.
7. Add `paginate_with_joins`, migrate `FloorRepository`/
   `ReceptionDeskRepository`.
8. Reduce `provision_branch`'s flush count.

Each step is independently revertible (`git revert` the one commit) without
touching the others, since none depends on another's code existing.

## Open Questions

None — every fix above has a concrete decision and a verification path;
nothing here needs to be deferred past `tasks.md`.
