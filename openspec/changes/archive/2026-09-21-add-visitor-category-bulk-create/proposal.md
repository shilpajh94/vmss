## Why

An admin who needs to add many Visitor Categories at once (e.g. onboarding a
tenant with an existing list of 20+ category names) has no way to do it but
one `POST /visitor-categories` — and one admin-UI form submission — per
category. For a real-world list this size, that's a lot of repetitive,
error-prone manual entry for data that's just a list of names.

## What Changes

- New bulk-create capability for Visitor Categories: an admin submits a list
  of category names in one request/UI action, and the system creates a
  `VisitorCategory` for each name that doesn't already exist (by name or by
  its derived code), skipping — not failing the whole batch on — any name
  that collides with an existing category.
- A category's `code` is derived from its `name` the same way a Form
  Builder custom field's `key` is derived from its `label` today
  (`AddFieldModal.tsx`'s `slugify`) — lowercase, non-alphanumeric runs
  collapsed to `_`, leading/trailing `_` trimmed — since the bulk flow only
  collects names, not a separate code per category.
- The response reports what happened per name: created, or skipped because
  a category with that name (or derived code) already exists — not just an
  aggregate count — so the admin can see exactly which of their pasted names
  landed and which didn't.
- Admin UI: the Visitor Categories page gains a "Bulk Add" action (a
  textarea, one category name per line) alongside the existing single "Add
  Category" flow — it doesn't replace it, since a single category also
  wants its badge color/NDA/escort/duration set at creation, which bulk-add
  doesn't collect.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `visitors`: adds a bulk-create path to the existing "Visitor Category CRUD
  With a Configurable Form Schema" capability area — creating many
  categories (name-only) in one call, with per-item duplicate handling
  distinct from the existing single-create endpoint's all-or-nothing 409.

## Impact

- **Backend (`VMSS_API`)**: `src/vmss_api/visitors/schemas.py` (new
  `VisitorCategoryBulkCreate`/`VisitorCategoryBulkCreateResult` shapes),
  `src/vmss_api/visitors/service.py` (new bulk-create function, reusing
  `VisitorCategoryRepository.get_by_code`/`get_by_name`), `src/vmss_api/
  visitors/router.py` (new `POST /visitor-categories/bulk` endpoint, same
  `visitor-categories:manage` permission as single create).
- **Frontend (`VMMS_WEB`)**: `src/presentation/pages/admin-visitor-
  categories/` gains a "Bulk Add" modal/action and its own use-case/
  repository method calling the new endpoint; results (created vs. skipped)
  are shown to the admin after submit.
- **Data**: no migration — reuses the existing `VisitorCategory` table and
  its existing unique constraints on `name`/`code`.
- **Not in scope**: badge color, NDA requirement, escort requirement, and
  max duration are not collected by bulk-add; a bulk-created category gets
  the same defaults (`null`/unset) a single-create request would get if
  those fields were omitted. An admin who wants those set per-category still
  edits it individually afterward via the existing single-record form.
