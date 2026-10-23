## Why

The invitation board's filter bar (Purpose, Type, Status, Source) uses native `<select>` elements: the open list is the browser's default menu, unstyled and inconsistent with the rest of the UI, and each filter can hold only one value. Staff and admins often need "Approved *and* Checked-in" or "Individual *and* Group from two purposes" and currently have to flip filters one at a time.

## What Changes

- Replace the four native-`<select>` dropdowns in `BoardFilterBar` with a themed, custom **multi-select dropdown**: pill trigger with icon + summary + chevron, a floating panel with a checkbox row per option, "Clear" inside the panel, closes on outside click / Esc, fully keyboard operable.
- Trigger summary: "All purposes" when nothing selected, the option label when one is selected, "Label +N" (or a count badge) when several.
- Each filter now holds a **set** of values. The board loads every selected value: invitations matching *any* selected value within a filter, and *all* filters combined (AND across filters, OR within one).
- Because the backend list endpoint accepts only one value per filter, the frontend **fans out** one request per selected-value combination per column and merges the results. No backend change.
- Status multi-select shows several board columns at once (only the selected statuses load; others stay empty).
- "Clear filters" and the "is filtering" indicator reset/detect all four sets. The `?status=` deep link seeds a one-item status set.
- Export invitations: the dialog's filter summary lists all selected values; export stays single-valued per backend (see design), so the dialog asks the user to narrow a multi-valued filter before exporting.
- Calendar, audit and dashboard `DropdownFilter` users are unchanged.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `admin-invitations`: "Search and filters sit in one inline bar…" and the status-filter column-loading requirement change to multi-select, styled dropdowns.
- `staff-dashboard`: the staff board uses the same shared filter bar, so its filter requirement changes the same way.

## Impact

- Code: `src/presentation/components/invitation-board/BoardFilterBar.tsx`, `filter-options.ts`; new `src/presentation/components/ui/MultiSelectFilter.tsx`; `src/presentation/hooks/use-invitations-board.ts`, `use-paged-board-columns.ts`; `ExportInvitationsModal.tsx`; `admin-invitations.tsx`, `staff-invitations.tsx`.
- APIs: none changed. Request volume per board load rises with number of selected-value combinations (capped).
- Dependencies: none added.
