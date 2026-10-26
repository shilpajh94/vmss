## 1. MultiSelectFilter component

- [x] 1.1 Create `src/presentation/components/ui/MultiSelectFilter.tsx`: trigger button (icon, summary, chevron, optional count), floating checkbox panel with "Clear", Esc / outside-click close, arrow/Space/Enter keyboard handling, ARIA (`aria-haspopup`, `aria-expanded`, `listbox`/`option`, `aria-multiselectable`), theme-token styling, full-width on mobile
- [x] 1.2 Summary logic (`allLabel` / label / "label +N") and normalise "all options ticked" to empty
- [ ] 1.3 (blocked: repo has no unit-test runner) Unit tests for selection, summary text, Esc/outside close, keyboard toggle

## 2. Filter state and options

- [x] 2.1 Change `use-invitations-board.ts` filter state to `string[]`; seed `?status=` as a one-item array; update `isFiltering` and `clearFilters`
- [x] 2.2 Drop the "All …" pseudo-options and `'all'` sentinel from `filter-options.ts` / `purposeOptions`; pass `allLabel` instead
- [x] 2.3 Update `BoardFilterBar` and `BoardExtraFilter` to use `MultiSelectFilter` with `values`/`onChange`; update `boardExtraFilters` and the staff/admin pages

## 3. Multi-value loading

- [x] 3.1 Make `ColumnQuery` carry `purposeOfVisit[]`, `registrationType[]`, `source[]`; add a combination builder (cartesian product, cap 24)
- [x] 3.2 Update `usePagedBoardColumns` (`reload`, `fetchWindow`, `loadMore`) to fan out per combination, sum totals, dedupe by id, interleave by rank
- [x] 3.3 Derive `visibleStatuses` and `focusClosedStatus` from the status set
- [ ] 3.4 (blocked: repo has no unit-test runner) Tests for merge/total/dedupe, single-value regression, status multi-select columns, cap behaviour

## 4. Export

- [x] 4.1 Update `exportFilterSummary` to list all selected values
- [x] 4.2 In `ExportInvitationsModal`, show the "one value per filter" note and disable Export when any filter is multi-valued; keep single-value export unchanged
- [ ] 4.3 (blocked: repo has no unit-test runner) Test the disabled/enabled export states

## 5. Verification

- [ ] 5.1 Manually check admin and staff boards at 1440px, 1024px and mobile width (wrapping, panel overlap with sticky headers, light/dark theme)
- [x] 5.2 Run lint, typecheck and the test suite (no test runner is configured in this repo; tsc and lint pass)
