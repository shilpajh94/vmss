## 1. Backend Schemas

- [x] 1.1 In `src/vmss_api/visitors/schemas.py`, add `VisitorCategoryBulkCreate`
      (`names: list[str]`, min length 1 after validation, each name
      max_length 100 matching `VisitorCategoryCreate.name`).
- [x] 1.2 Add `VisitorCategoryBulkCreateItemStatus` (`StrEnum`: `created`,
      `skipped`) and `VisitorCategoryBulkCreateItem` (`name: str`,
      `status: VisitorCategoryBulkCreateItemStatus`, `reason: str | None`,
      `category: VisitorCategoryOut | None` — populated when `created`).
- [x] 1.3 Add `VisitorCategoryBulkCreateOut` (`items:
      list[VisitorCategoryBulkCreateItem]`, `createdCount: int`,
      `skippedCount: int`).
- [x] 1.4 Reject an empty or all-blank `names` list with a `model_validator`
      (422), mirroring `FormFieldCreate._check_options`'s pattern of a
      `model_validator(mode="after")` raising `ValueError`.

## 2. Backend Service and Slugify Helper

- [x] 2.1 Add a small `_slugify(name: str) -> str` helper in
      `visitors/service.py` (lowercase, collapse non-`[a-z0-9]` runs to
      `_`, trim leading/trailing `_`) — same algorithm as
      `AddFieldModal.tsx`'s `slugify`, reimplemented server-side since this
      is a backend-only endpoint.
- [x] 2.2 Add `bulk_create_visitor_categories(tenant_db, payload) ->
      VisitorCategoryBulkCreateOut`: for each name (trimmed, skip blank
      entries), derive its code via `_slugify`, check
      `VisitorCategoryRepository.get_by_name`/`get_by_code` (both against
      the database AND against categories already created earlier in this
      same call, to catch within-batch duplicates per design.md), and
      either insert (reusing `create_visitor_category`'s field-population
      logic minus its own pre-check, since this function does its own) or
      record a `skipped` item with a `reason` ("name already exists" /
      "code already exists" / "duplicate in this request").
- [x] 2.3 Commit once after processing the whole batch (per
      `query-performance.md` §3 — one commit per logical operation, not one
      per row); wrap in the same `_commit_or_conflict`-style residual-race
      handling as `create_visitor_category`, but on that final commit
      failing, do not silently drop which items would have been affected —
      surface a 409 for the whole request in that (rare, race-only) case,
      consistent with how a raced single-create already behaves.

## 3. Backend Router

- [x] 3.1 Add `POST /api/v1/visitor-categories/bulk` in
      `visitors/router.py`, `dependencies=[Depends(require_permission(
      "visitor-categories:manage"))]` (same permission as single create),
      `response_model=Envelope[VisitorCategoryBulkCreateOut]` per
      `api-documentation.md` §1, returning `success_response(data=...)`.
      Also queues one `visitor_category_created` audit entry per created
      category, matching single-create's per-category audit trail
      (security-architecture.md §5) — not called out explicitly in this
      task originally, added as a natural extension of the same pattern.
- [x] 3.2 Route it under the existing `category_router`
      (`prefix="/visitor-categories"`) so it's covered by the existing
      router registration — no new `api.py`/`main.py` changes needed.

## 4. Backend Tests (`visitors/tests.py`)

- [x] 4.1 Happy path: all-new names all get created, response reports each
      as `created` with its `category` populated, `createdCount` matches.
- [x] 4.2 Some names already exist (by name and, separately, by derived
      code colliding with an existing category's code): those are
      `skipped` with a reason, the rest are created, no exception raised.
- [x] 4.3 A duplicate name within the same request's list: first occurrence
      created, second occurrence `skipped` with a "duplicate in this
      request" reason.
- [x] 4.4 Empty list and all-blank-entries list are both rejected with 422.
- [x] 4.5 Permission-denied case: a caller without `visitor-categories:manage`
      gets 403 (per `testing-standards.md` §2).
- [x] 4.6 Tenant-isolation case: bulk-creating in one tenant's schema does
      not create or collide against another tenant's identically-named
      category (per `testing-standards.md` §2, using the
      `make_tenant_schema`/`open_tenant_session` fixtures).

## 5. Frontend: Domain Types and Repository

- [x] 5.1 In the visitor-category domain schema/types file (mirroring
      `form-builder-schema.ts`'s pattern), add
      `VisitorCategoryBulkCreateInput` (`names: string[]`) and
      `VisitorCategoryBulkCreateResult` (per-item outcome list + counts),
      zod-parsed the same way existing visitor-category responses are.
- [x] 5.2 Add a `bulkCreate` method to the visitor-category repository
      interface and its HTTP implementation, calling the new endpoint.
- [x] 5.3 Add a `BulkCreateVisitorCategoriesUseCase` (or equivalent),
      mirroring the existing single-create use-case's structure.

## 6. Frontend: Bulk Add UI

- [x] 6.1 Add a "Bulk Add" action to the admin Visitor Categories page,
      alongside the existing "Add Category" action — a modal with a
      textarea (one name per line) and a submit button.
- [x] 6.2 On submit, call the new use-case and show the per-name result
      (created vs. skipped, with reason) so the admin can see exactly what
      happened; refresh the categories list/table to include the newly
      created ones.
- [x] 6.3 Client-side: reject submission if the textarea is empty or only
      blank lines (mirroring the backend's 422), matching this codebase's
      existing pattern of disabling submit until required input is present
      (e.g. `AddFieldModal`'s label-required check).

## 7. Documentation

- [x] 7.1 Update `docs/features/visitors.md` to document the new bulk-create
      endpoint, its request/response shape, the skip-not-fail duplicate
      behavior, and that badge color/NDA/escort/duration aren't collected
      by this path.
