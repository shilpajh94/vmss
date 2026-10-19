## 1. Data layer

- [x] 1.1 Add `sortBy?: 'submitted_at' | 'created_at' | 'status_changed_at'`
  and `sortOrder?: 'asc' | 'desc'` to `ListVisitRequestsParams` in
  `src/data/repositories/visit-request-summary-repository.ts`.
- [x] 1.2 Pass `sortBy` and `sortOrder` through in `queryParams` in
  `src/infrastructure/visit-request-summary-repository.ts`'s `list`.

## 2. Board columns

- [x] 2.1 In `src/presentation/hooks/use-paged-board-columns.ts`, add the
  `BOARD_SORT` constant and a `columnPageParams` helper (design.md
  Decision 1).
- [x] 2.2 Route all three `fetchPage` calls through the helper: both
  branches of `fetchWindow`, and `loadMore`.

## 3. Verification

- [x] 3.1 Run `npm run build` (tsc) and `npm run lint`. Do not run
  prettier (the repo has none).
- [x] 3.2 Against the local API with the paired API change applied,
  confirm in the browser network tab that each column request on
  `/staff/invitations` and the admin Invitations board carries
  `sortBy=status_changed_at&sortOrder=desc`, including load-more and
  refresh.
- [x] 3.3 With seeded data, check in an invitation that was submitted
  earlier than other checked-in ones, and confirm it appears at the top
  of Checked-in on both boards. Do the same for approve (Approved) and
  check-out (Closed → Checked-out).
- [x] 3.4 Run the existing Playwright suite (`npm run e2e`) for the
  invitation lifecycle and live dashboards. Do not run it at the same
  time as API pytest (shared Redis rate limits).

## 4. Release

- [ ] 4.1 Confirm the target environment's API accepts
  `GET /invitations?sortBy=status_changed_at` (not a 422) before merging
  or deploying this change.
