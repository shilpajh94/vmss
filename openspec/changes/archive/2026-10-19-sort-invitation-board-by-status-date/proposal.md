## Why

Every status column on the admin and staff invitation boards (Requested,
Approved, Checked-in, Checked-out, Denied, Archived) is a separate
`GET /invitations?status=<x>` call that sends no `sortBy`. Each column
therefore gets the endpoint's default order, `submittedAt DESC`: the date
the visitor *submitted the request*, not the date the invitation moved
into that column. So a visitor who checked in two minutes ago, but whose
request was submitted last week, sits below someone who checked in hours
ago but submitted yesterday. The same applies to approvals, check-outs,
denials, and archiving. Front-desk staff read each column as "latest
activity first", and today it isn't. The query also has no tie-breaker,
so rows with equal timestamps can repeat or go missing between pages as
the board loads more on scroll.

## What Changes

- `GET /invitations` accepts a new whitelisted `sortBy` value,
  `status_changed_at`. It orders each invitation by the time it entered
  its **current** status:
  - `submitted` → `submittedAt` (or `approvalRevertedAt`, if the
    approval was later reverted)
  - `approved` → `approvedAt`
  - `checked_in` → `checkedInAt`
  - `checked_out` → `checkedOutAt`
  - `denied` → `deniedAt`
  - `archived` → `archivedAt`

  If that timestamp is missing, the order falls back to `submittedAt`,
  then `createdAt`.
- Every `GET /invitations` sort, old values included, gets a
  deterministic tie-breaker, so paging stays stable.
- The default `sortBy` stays `submitted_at`. The new behaviour is opt-in,
  so existing clients (Flutter, integrations) see no contract change.
- Each list row exposes `statusChangedAt`, the timestamp the row was
  sorted by, so a board card can show "checked in 2 min ago" without
  working it out on the client. This is an additive response field.
- The web boards (admin invitations and the staff/reception dashboard)
  switch their per-column queries to `sortBy=status_changed_at`. That
  work lands as a paired change in the `VMMS_WEB` repository.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `invitations`: the "Employee Lists Invitations at Their Authorized
  Branches" listing gains the `status_changed_at` sort option, stable
  tie-breaking, and the `statusChangedAt` row field.

## Impact

- **API**:
  - `src/vmss_api/invitations/schemas.py`: `InvitationSortableField`
    gains the new value, and `InvitationListItemOut` gains
    `status_changed_at`.
  - `src/vmss_api/invitations/repository.py`: the `list_page` sort
    expression and tie-breaker.
  - `src/vmss_api/invitations/router.py`: list row mapping.
  - `docs/features/invitations.md`: the sort table.
- **Web (paired change in VMMS_WEB)**:
  - `use-paged-board-columns.ts` / `visit-request-summary-repository.ts`
    pass `sortBy`.
  - The `admin-invitations` and `staff-dashboard` specs.
- **Compatibility**: additive only. There is no new `/api/v2`, and the
  default order is unchanged.
- **Database**: no migration. The sort uses existing timestamp columns.
