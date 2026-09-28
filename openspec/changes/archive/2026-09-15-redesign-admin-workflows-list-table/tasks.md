## 1. Hook: derive status and paginate

- [x] 1.1 In `use-admin-workflows.ts`, extend `WorkflowGroup` with `status: 'active' | 'paused'`, computed from the group's levels' `isActive` (requires exposing `isActive` through `WorkflowLevelView`, sourced from `ApprovalWorkflowRule.isActive`).
- [x] 1.2 Add pagination state (`page`, fixed `pageSize`) and a derived current-page slice of `workflows`, plus `goToNextPage` / `goToPreviousPage` callbacks that respect first/last page bounds.
- [x] 1.3 Reset `page` to the first page whenever `workflows` reloads (e.g. after delete) so the footer caption and slice stay consistent.

## 2. Component: WorkflowListTable

- [x] 2.1 Create `src/presentation/pages/admin-workflows/Components/WorkflowListTable.tsx` replacing `WorkflowGroupList.tsx`: card wrapper, card header ("Workflow List" title + "N workflows" subtitle), table with Workflow/Status/Approval Flow/Levels/Actions columns.
- [x] 2.1a Remove the Export/Filter toolbar buttons from the card header per admin feedback (not reproduced from the Figma reference).
- [x] 2.2 Render the Status badge per row from `workflow.status` ("Active" / "Paused" styles consistent with existing badge patterns in the design system).
- [x] 2.3 Render the Approval Flow cell by joining `workflow.levels` (in order) with " → ", and the Levels cell as "N levels".
- [x] 2.4 Keep row Edit/Delete actions wired to the existing `navigate(...)` and `onDelete` handlers unchanged.
- [x] 2.5 Render the card footer with "Showing X–Y of N workflows" and Previous/Next buttons wired to the hook's pagination callbacks, disabled at the first/last page.
- [x] 2.6 Delete `WorkflowGroupList.tsx` and update its import in `admin-workflows.tsx`.

## 3. Page header restyle

- [x] 3.1 In `admin-workflows.tsx`, add the header subtitle "Review active workflows, monitor status, and manage approvals across the organization" under the "Workflows" title.
- [x] 3.2 Replace the "Filters" button with a "Refresh" button that calls the existing `retry()` loader.
- [x] 3.3 Rename "Add Workflow" to "Create Workflow" (button label and `aria-label`), keeping its existing navigation to `/admin/workflows/new`.

## 4. Verification

- [x] 4.1 Run the app and visually compare `/admin/workflows` against the Figma frame (node 268:5) for the table layout, badges, and footer.
- [x] 4.2 Verify empty-state, loading, and error-state rendering still work unchanged with the new header/table structure.
- [x] 4.3 Verify delete confirmation, edit navigation, and "Create Workflow" navigation still work end-to-end.
- [x] 4.4 Verify pagination Previous/Next disable correctly at the first/last page and the "Showing X–Y of N" caption updates without a network request.
