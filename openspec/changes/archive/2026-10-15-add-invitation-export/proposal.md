## Why

VMSS_API now has `GET /api/v1/invitations/export` (its `add-invitation-export`
change). It returns invitations as CSV or XLSX, one row per visitor, filtered
by status and a date range. Nothing in the web portal calls it yet, so staff
still can't export "everyone who checked in today" or "approved visitors this
week" without going to the API directly.

## What Changes

- An **Export** button in the invitation board's toolbar:
  - on the admin Invitations board (`/admin/invitations`), for admins, and
  - on the staff dashboard (`/staff/dashboard`), shown only to Reception.
    Hosts never see it, because the API would return 403 for them.
- The button opens an **Export invitations** dialog. The dialog is
  prefilled from the board's current state, and the user can change:
  - **Status**: "All statuses", Requested, Approved, Checked-in,
    Checked-out or Denied. It is prefilled from the board's Status filter
    where the board has one; the staff dashboard has none, so it defaults
    to All.
  - **From / To** dates (optional), with a short hint that the range
    applies to the chosen status's date, for example the check-in date.
  - **Format**: CSV or Excel, defaulting to CSV.
- The board's other active filters (search, purpose, registration type,
  source) and its scope are passed along unchanged. The staff dashboard
  sends `relevantToMe=true`, matching what that board shows. The dialog
  shows these filters as a read-only summary so the user knows what the
  file will contain.
- Confirming downloads the file with a clear filename, for example
  `invitations-checked_in-20261014.xlsx`.
  - While the file downloads, the dialog shows a busy state and blocks a
    second click.
  - If the API rejects the request (too many rows, permission denied, an
    invalid date range), the dialog stays open and shows the server's
    message.
- The dialog checks that From is not later than To before sending the
  request.

No API change is needed. The web app builds the filename itself, because
the API doesn't expose `Content-Disposition` through CORS.

## Capabilities

### New Capabilities
<!-- None: the export is a feature of the existing boards. -->

### Modified Capabilities
- `admin-invitations`: the board's toolbar gains an Export action and the
  Export invitations dialog.
- `staff-dashboard`: the board's toolbar gains the same Export action and
  dialog, shown only to Reception.

## Impact

- **Code:**
  - `src/data/api/api-endpoints.ts`: a new `EXPORT_INVITATIONS` endpoint.
  - A repository method plus `ExportInvitationsUseCase` in `src/data/`, an
    HTTP implementation in `src/infrastructure/`, and wiring in
    `composition-root.ts`. The download reuses `ApiClient.downloadBlob`.
  - A new `ExportInvitationsModal` in
    `src/presentation/components/invitation-board/`.
  - Export state in `use-invitations-board.ts`.
  - An Export button on both board pages.
- **Depends on:** the VMSS_API `add-invitation-export` change being
  deployed, including its tenant migration that grants `invitations:export`.
- **No new dependencies.**
