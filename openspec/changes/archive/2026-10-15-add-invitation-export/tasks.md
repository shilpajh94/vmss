## 1. Data Layer

- [x] 1.1 Add `EXPORT_INVITATIONS` (`GET /invitations/export`, `hasToken: true`) to `src/data/api/api-endpoints.ts`
- [x] 1.2 Define `InvitationExportParams` (status, dateFrom, dateTo, format `'csv' | 'xlsx'`, registrationType, source, search, purposeOfVisit, relevantToMe) and add `export(params): Promise<Blob>` to `VisitRequestSummaryRepository` in `src/data/repositories/`
- [x] 1.3 Implement `export` in `src/infrastructure/visit-request-summary-repository.ts` through `apiClient.downloadBlob`, leaving undefined params out
- [x] 1.4 Add `ExportInvitationsUseCase` in `src/data/use-cases/`, wire it in `composition-root.ts`, and expose it through `useAppDependencies()`

## 2. Shared Helpers

- [x] 2.1 Add a `saveBlob(blob, filename)` utility in `src/presentation/utils/` and switch the audit-trail download hook to it
- [x] 2.2 Move the status and source option lists from `admin-invitations.tsx` into `components/invitation-board/filter-options.ts`, and add the status-to-date-hint map and an `exportFilename(status, format)` helper (local `YYYYMMDD`)

## 3. Export Dialog

- [x] 3.1 Create `ExportInvitationsModal` in `components/invitation-board/` with:
  - a Status select (with "All statuses"), From/To date inputs with the status-specific hint, and a CSV/Excel `SegmentedToggle`;
  - the read-only summary of other board filters ("No other filters" when there are none);
  - a busy confirm button.

  Its form state is local and re-initialised from `initialStatus` each time it opens.
- [x] 3.2 Add the inline From > To validation that disables confirm, and an error area showing `errorMessage`
- [x] 3.3 Check the dialog at 360px and 1440px wide: it is a bottom sheet on narrow screens and has no horizontal scroll

## 4. Board Integration

- [x] 4.1 In `use-invitations-board.ts`, add `canExport` (admin board → `isAdmin`, staff board → `isReception`), open/close state, `isExporting`, `exportError`, and `exportInvitations(choice)`, which combines the dialog's choice with the current `columnQuery` (including `relevantToMe`) and guards against a second export while one is in flight
- [x] 4.2 On success: call `saveBlob` with `exportFilename(...)`, close the dialog and show a success toast. On an `ApiError`: keep the dialog open and set `exportError` to the server message.
- [x] 4.3 Admin Invitations page: add the Export button beside `BoardFilterBar`, visible while loading or in error state. Pass the board's Status filter as `initialStatus`, plus the filter summary.
- [x] 4.4 Staff dashboard: render the same button only when `canExport` is true, with `initialStatus` set to All

## 5. Verification

- [x] 5.1 `npm run lint` and `npm run build` (type check) both clean
- [x] 5.2 Manually check against a local API that has `add-invitation-export` deployed:
  - an admin exports Checked-in for one day as Excel, and the file opens with the expected rows and filename;
  - an over-cap export (lower `INVITATION_EXPORT_MAX_ROWS` locally) shows the API's message in the dialog;
  - From > To is blocked;
  - Reception sees Export on the staff dashboard and gets only their board's invitations;
  - a host sees no Export button.
- [x] 5.3 Update `CHANGELOG.md` with the new Export action

## 6. Responsive Pass

- [x] 6.1 Remove `BoardFilterBar`'s forced single row (`lg:`/`xl:flex-nowrap`), which clipped the staff Export button at 1024px and, already before this change, the admin Source dropdown at 1280px and "Clear filters" at 1280–1440px. Right-align the trailing action when it wraps; it spans full width on phones.
- [x] 6.2 Run a browser check at 360/390/640/768/1024/1100/1280/1366/1440/1920px on both boards (unfiltered, filtered, dialog open): no page-level sideways scroll, no clipped header controls, and the admin bar still on one row at 1440px with no filters

