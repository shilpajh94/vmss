## Context

See proposal.md - Why. The Figma `workflow-builder` frame (node 268:5) covers only the Workflows list content area; its Sidebar and TopBar frames already match the built `AdminSidebar`/`AdminTopBar` components, so no changes are needed there. The existing `use-admin-workflows.ts` hook already assembles `WorkflowGroup[]` (category name + ordered `WorkflowLevelView[]`) from `listApprovalWorkflowRulesUseCase`, `listVisitorCategoriesUseCase`, and `listRolesUseCase` — none of that data-loading logic changes; only what's derived from it and how it's rendered changes.

## Goals / Non-Goals

**Goals:**
- Match the Figma table layout (Workflow / Status / Approval Flow / Levels / Actions columns, card toolbar, pagination footer) using only data already available on `WorkflowGroup`.
- Keep all existing load/error/empty/create/edit/delete behavior from `admin-approval-workflows` intact.

**Non-Goals:**
- No new backend fields, endpoints, or status enum — Status is a pure derivation from existing `isActive` booleans (per per-question answer).
- No Export/Filter/search toolbar — dropped from the Figma reference per admin feedback rather than shipped as non-functional placeholders.
- No changes to the Add/Edit Workflow form page.

## Decisions

- **Status derivation lives in the hook, not the component.** `useAdminWorkflows` computes `status: 'active' | 'paused'` per `WorkflowGroup` (all levels `isActive` → `active`, else `paused`) so the table component stays presentational and the derivation is unit-testable in one place.
- **Pagination is client-side state in the hook.** `WorkflowGroup[]` is already fully loaded before render (no server pagination today), so a `page` state + fixed `pageSize` (matching Figma's 4-per-page) slice the already-grouped array. This avoids inventing query params or a paginated endpoint that doesn't exist.
- **Table replaces `WorkflowGroupList` as a new `WorkflowListTable` component**, rather than reshaping `WorkflowGroupList` in place, because the layout (table semantics, footer) is different enough that evolving the old component would leave dead card-layout code paths behind.
- **Export/Filter buttons from the Figma reference are omitted entirely**, not built as inert placeholders — the current "Filters" button on the Workflows page already sets that precedent, but on review the admin asked for these not to be reproduced here.

## Risks / Trade-offs

- [Status badge may read "Paused" for workflows that were simply configured with one intentionally-inactive/optional rule, not an actually-paused workflow] → Documented in the spec as a direct derivation from `isActive`; if product later needs a real workflow-level status, that's a backend change and a follow-up proposal, not something to guess at here.
- [Client-side-only pagination hides workflows beyond the current in-memory load if the backend ever paginates `listApprovalWorkflowRulesUseCase`] → Out of scope; today's use case returns the full list, so this is safe as implemented.
