## Context

See `proposal.md` - Why. This is the fourth Admin-section page, building on `admin-organisation-configs`, `admin-branches`, and `admin-departments`:

- `AdminSidebar` already declares `'buildings'` in `AdminSidebarActiveItem` and renders the "Buildings" nav item, but `handleActivate` has no case for it — same gap already fixed for `branches`/`departments`.
- `AdminTopBar`, `Modal`, `ConfirmDialog`, `LoadingState`, `EmptyState`, `TextField`, `SelectField`, `ToggleSwitch` are all established shared primitives; this page introduces no new shared UI, only page-local components for the floor/checkpoint sub-forms.
- `admin-branches` already exposes `listBranchesUseCase`, reused here the same way `admin-departments` reused it.
- `admin-departments` established: one page for Add/Edit (no breadcrumb top-bar conflict), a route-param-driven form hook that fetches the full list and finds by id in edit mode, and denormalized read-only display fields (`branchName`, `employeeCount`) that the form never edits — `admin-buildings` follows the same shape for `branchName` and adds `receptionDesks` to that read-only-display category.
- The user confirmed (see conversation): Floors and Checkpoints are full nested CRUD, added/renamed/removed entirely client-side and only persisted on "Save Building"; Add/Edit Floor and Add/Edit Checkpoint each use a small `Modal`-based name-only form, since no design exists beyond the plain name shown in the list rows.

## Goals / Non-Goals

**Goals:**
- Match both Figma designs (Buildings Registry list and Add/Edit Building) pixel-for-pixel, including the expand/collapse floor cards.
- Model Floors and Checkpoints as nested arrays owned by the Building record — no separate CRUD endpoints for them.
- Reuse every existing shared primitive; only add page-local components for the floor/checkpoint modals.

**Non-Goals:**
- No Reception Desks capability — the list's "Reception Desks" column is read-only, backend-supplied display data, exactly like Employee Count in `admin-departments`. No admin-buildings UI writes to it.
- No Security Gates capability — despite the sidebar nav item existing, checkpoints here are building-local data, not a link to a future "Security Gates" page.
- No drag-to-reorder floors or checkpoints — the design shows a plain list; add/remove/rename only.

## Decisions

- **Floors and checkpoints are nested arrays in `BuildingInput`, not separate resources.** The Figma form has one "Save Building" action for the whole card — there's no independent per-floor or per-checkpoint save. `Floor` and `Checkpoint` need no separate "input vs. record" schema split (unlike `Building` itself, which has server-owned `branchName`/`receptionDesks`): every field on a floor or checkpoint is admin-editable, so one shared schema serves both reading and writing them.
- **Client-generated ids for new floors/checkpoints.** Since floors/checkpoints are created locally before any network call, each gets a `crypto.randomUUID()` id at creation time (matching the existing pattern used for toast ids in `toast-context.tsx`) so the UI has stable React keys and a target for edit/delete, whether or not the backend later replaces it. On edit-mode load, existing floors/checkpoints keep the ids the backend returned.
- **`totalFloors` is derived, not a schema field.** The list table's "Total Floors" column reads `building.floors.length` directly — carrying a separately-submitted count invites drift from the actual floors array. If the backend's list response is ever lighter-weight than the full floors array, this decision will need revisiting (see Risks).
- **One page for Add and Edit**, routed as `/admin/buildings/new` and `/admin/buildings/:id/edit`, following the exact `admin-departments` precedent (same top-bar mode, same "fetch full list, find by id" pattern for edit-mode loading via `listBuildingsUseCase`).
- **Floor and Checkpoint modals are page-local components (`FloorModal.tsx`, `CheckpointModal.tsx`), not new shared UI.** Each is a `Modal` wrapping a single `TextField` (name) plus Cancel/Save — the same shape as `BranchFormModal` before it grew more fields, but simple enough here to not warrant a shared "single-field modal" abstraction. Reusing `Modal` (not building new dialog chrome) keeps them consistent with `ConfirmDialog`.
- **Floor expand/collapse state lives in the form hook, keyed by floor id**, not on the `Floor` data itself — matching the Figma's implication that expand/collapse is a UI-only concern (collapsed "First Floor" in the screenshot still has checkpoints conceptually, just hidden).
- **Deleting a floor deletes its checkpoints too**, with a single confirmation covering both (no separate "this floor has checkpoints" warning) — the design shows one delete icon per floor, not a cascading-impact warning.

## Risks / Trade-offs

- [`totalFloors` derived from a client-held floors array] → If a future backend optimizes the list endpoint to omit full floor detail, the list page would need its own lightweight count field instead of relying on `floors.length`; not needed today since the Figma list only shows a count, and the full detail is naturally available once a building is loaded for editing.
- [Client-generated ids for new floors/checkpoints] → If the backend rejects client-supplied ids for new records, the create/update payload can simply omit `id` for entries with a client-only marker; deferred until a real backend contract is known.
- [Reception Desks and Security Gates are out of scope, read-only or absent] → Consistent with how `admin-departments` treated Employee Count; revisit once those sidebar sections get their own capabilities.
