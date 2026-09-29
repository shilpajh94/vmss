## Why

The Workflows list at `/admin/workflows` currently renders each visitor category's approval chain as a stacked card with an inline numbered list. The approved Figma design (`workflow-builder`, node 268:5) replaces this with a denser "Workflow List" table card — Workflow / Status / Approval Flow / Levels / Actions columns, a card-level toolbar (Export, Filter), and pagination — inside a restyled page header (Refresh, Create Workflow). Aligning the built page with this design is the ask.

## What Changes

- Replace the page header's "Filters" / "Add Workflow" buttons with "Refresh" (re-runs the existing load) and "Create Workflow" (same navigation as today's Add Workflow), and add a header subtitle ("Review active workflows, monitor status, and manage approvals across the organization").
- Replace `WorkflowGroupList`'s stacked-card layout with a single "Workflow List" card containing:
  - A card header with a live count subtitle ("N workflows").
  - A table with columns Workflow, Status, Approval Flow, Levels, Actions.
  - A Status badge per row derived from the group's rules: **Active** when every rule in the group has `isActive: true`, otherwise **Paused**. (Figma's "Draft" state and the "newly created" count are not backed by any field on `ApprovalWorkflowRule` — no `status` enum or `createdAt` — so they are dropped rather than fabricated.)
  - An "Approval Flow" cell joining each level's approver role name with " → " (e.g. "Reception → Manager → Host").
  - A "Levels" cell showing "N levels".
  - Row Edit/Delete actions, same handlers as today (navigate to edit, open the existing delete confirmation dialog).
  - A footer with a "Showing X–Y of N workflows" caption and Previous/Next controls that paginate the already-loaded, already-grouped workflow list client-side (no new API calls or params).
- Figma's Export and Filter toolbar buttons are dropped rather than built as non-functional placeholders — the admin asked for them to be removed rather than shipped inert.
- The Add/Edit Workflow form page, the Admin sidebar, and the Admin top bar are out of scope — Figma's sidebar/top bar chrome already matches `AdminSidebar/AdminTopBar` as built.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `admin-approval-workflows`: the Workflows list's rendering changes from grouped stacked cards to a single table card (Workflow/Status/Approval Flow/Levels/Actions columns, header toolbar, client-side pagination); a derived Status badge is introduced; loading/error/empty/create/edit/delete behavior is unchanged.

## Impact

- `src/presentation/pages/admin-workflows/admin-workflows.tsx` — page header restyle (Refresh + Create Workflow, subtitle), swaps in the new table component.
- `src/presentation/pages/admin-workflows/Components/WorkflowGroupList.tsx` — replaced by a new table-card component (e.g. `WorkflowListTable.tsx`); old component removed.
- `src/presentation/pages/admin-workflows/hooks/use-admin-workflows.ts` — add a derived `status` (`active` | `paused`) per `WorkflowGroup` and client-side pagination state (page, pageSize, page slice); existing load/delete logic unchanged.
- No changes to `src/domain/`, `src/data/`, or `src/infrastructure/` — no new endpoints, schemas, ports, or use cases; all data needed already comes from `listApprovalWorkflowRulesUseCase` / `listVisitorCategoriesUseCase` / `listRolesUseCase`.
