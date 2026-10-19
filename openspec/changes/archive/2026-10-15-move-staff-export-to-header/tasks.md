## 1. Code

- [x] 1.1 `src/presentation/components/invitation-board/ExportInvitationsButton.tsx`: add an optional `compact` prop. In compact mode the label is `hidden md:inline`, `aria-label="Export"` is set, and the padding gives a roughly 40×40 icon button below `md`. The default rendering, used by admin, is unchanged.
- [x] 1.2 `src/presentation/pages/staff-dashboard/Components/WorkspaceHeader.tsx`: add an optional `leadingAction?: ReactNode` and render it first in the right-hand group, before Refresh.
- [x] 1.3 `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`:
  - Pass `leadingAction={canExport ? <ExportInvitationsButton compact onClick={openExport} /> : undefined}` to `WorkspaceHeader`.
  - Remove `trailingAction` from `BoardFilterBar`.

## 2. Reconcile pending planning artifacts

- [x] 2.1 In `openspec/changes/add-invitation-export/specs/staff-dashboard/spec.md`:
  - Change the requirement text from "last control in its search and filter bar" to the workspace-header placement.
  - Change the "Dialog opens with all statuses" scenario to open on the board's current Status filter.
  - Change the in-bar wrap scenario to the header/compact behavior.
  - Run `openspec validate add-invitation-export --strict`.
- [x] 2.2 In `openspec/changes/align-staff-board-filters-with-admin/specs/staff-dashboard/spec.md`:
  - Remove the Export button from "The workspace header and search bar are compact" and from its 1024px scenario.
  - Run `openspec validate align-staff-board-filters-with-admin --strict`.

## 3. Verify

- [x] 3.1 Run `npx tsc -b` and `npm run lint`. Both must be clean apart from pre-existing warnings. Do not run prettier.
- [x] 3.2 Browser check of the staff dashboard as a Reception user:
  - At 1440px, Export is in the header before Refresh and absent from the bar. With a Source filter set, the four filters stay on one row and only "Clear filters" is on the next line, matching admin.
  - At 1024px nothing clips.
  - At 360px Export is icon-only (accessible name "Export") and there is no horizontal scroll.
  - Export opens the dialog with the active Status preselected.
- [x] 3.3 Check as a host that no Export button shows anywhere, and that the admin Invitations Export button is unchanged.
