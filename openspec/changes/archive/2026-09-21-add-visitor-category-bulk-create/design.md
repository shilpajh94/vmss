## Context

`create_visitor_category` (`visitors/service.py:41-62`) is single-record:
pre-check `get_by_code`/`get_by_name` (both soft-delete-aware, per
`visitors/repository.py:35-45`), 409 if either collides, otherwise insert
and commit-or-409 on a residual race. The router
(`POST /visitor-categories`, `visitors/router.py:72-97`) requires
`visitor-categories:manage`. `VisitorCategoryCreate` requires both `name`
and `code` (`visitors/schemas.py:39-46`) — there's no server-side code
derivation today; every existing caller (the admin UI form) supplies both.

The admin UI's Form Builder already has a name → machine-key slugify
convention for exactly this kind of "derive an internal identifier from a
human-entered label" need
(`AddFieldModal.tsx`'s `slugify`: lowercase, `[^a-z0-9]+` runs → `_`,
trim leading/trailing `_`). See proposal.md for why bulk-create only
collects names (not full per-category records) and reuses that convention
for `code`.

## Goals / Non-Goals

**Goals:**
- One request creates many `VisitorCategory` rows from names alone.
- A name colliding with an existing category (by name or derived code) is
  reported and skipped, not a batch-failing error.
- Reuse the existing single-create path's duplicate-checking building
  blocks (`get_by_code`/`get_by_name`) rather than introducing new
  uniqueness-checking logic.

**Non-Goals:**
- Not collecting badge color/NDA/escort/duration in the bulk flow — see
  proposal.md's "Not in scope."
- Not replacing or changing `POST /visitor-categories` (single create) or
  its existing all-or-nothing 409 behavior — bulk-create is an additional
  endpoint, not a behavior change to the existing one.
- Not deduplicating or normalizing names beyond exact-string and
  derived-code matching (e.g. no fuzzy/case-insensitive matching of
  "Banking" vs. "banking " as the same category) — out of scope; an admin
  pasting near-duplicate names gets near-duplicate categories, same as if
  they'd created them one at a time today.

## Decisions

**Derive `code` from `name` via the same `slugify` convention as Form
Builder's field `key`, applied server-side.**
Alternatives considered: require the admin to type a code alongside each
name in the bulk textarea (rejected — defeats the point of a fast
paste-a-list flow, and the reported use case is a plain list of names with
no codes attached); auto-generate a random/opaque code instead of a
name-derived one (rejected — every other category's `code` today is a
short human-legible slug the admin themselves chose, e.g. matching the
name; an opaque code would be inconsistent and harder to recognize in the
admin list/table alongside hand-created categories).

**Skip-and-report, not fail-the-batch, on a collision.**
The single-create endpoint's all-or-nothing 409 makes sense for a form
submitting one category the admin is actively typing — a collision means
they should see the error and fix the field right there. A bulk paste of
20+ names is different: the whole point is unattended batch processing, so
one already-existing name shouldn't force the admin to remove it from the
textarea and resubmit everything else. Each name is checked and processed
independently; the response's per-name outcome list is what lets the admin
see what actually happened without needing to re-diff their input against
the category table afterward.

**Within-batch duplicates are handled by processing names in order and
checking against what's already been inserted so far in the same
transaction, not just what existed before the request.**
Two occurrences of "Banking" in one paste should not create two categories.
Processing sequentially (not concurrently) within one request naturally
makes each subsequent duplicate check see the earlier one, whether it was
already in the database or was just inserted earlier in this same request.

**One new schema pair, no change to the existing `VisitorCategoryCreate`/
`Out` shapes.**
`VisitorCategoryBulkCreate { names: list[str] }` (mirroring the plain
string-list shape `FormFieldCreate.options` already uses) and a per-name
result shape reporting `name`, `status` (`created`/`skipped`), and — when
skipped — a `reason`. The endpoint returns the full per-name report, not
just the created rows, so the admin UI can render "created: 19, skipped: 2
(already exist)" without a second lookup.

## Risks / Trade-offs

- [Risk] A name that derives to the same code as an existing category by
  coincidence (not because it's the same category) gets skipped even
  though the *name* itself was novel — e.g. "A/C Worker" and "A.C. Worker"
  both slugify toward the same code. → Mitigation: this mirrors exactly
  what would already happen if an admin manually typed a colliding code for
  a genuinely different name via the single-create form (409 on code
  already); accepted as consistent with existing single-create semantics,
  not a new failure mode introduced by bulk-create.
- [Risk] A very large pasted list (hundreds of names) processed
  sequentially, one query pair per name, could be slow. → Mitigation:
  accepted for this change's real-world scale (tens of names, per the
  proposal's example); not optimizing for a scale that isn't the reported
  use case.

## Migration Plan

No data migration — reuses the existing `VisitorCategory` table and its
existing unique constraints. New endpoint, additive to the existing
`visitors` router; no change to any existing endpoint's contract.
