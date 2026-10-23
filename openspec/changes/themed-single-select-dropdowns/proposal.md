## Why

The invitation board's filters now use a themed dropdown (`MultiSelectFilter`): rounded trigger, floating panel, hover/selected states. Every other dropdown in the app (e.g. the dashboard's "All branches" picker, calendar and audit filters, and all admin/wizard form selects) is still a native `<select>`, so the open list is the browser's default blue-highlight menu. It looks and feels different from the invitation page.

## What Changes

- Add a themed **single-select dropdown** that matches the invitation board's look: same trigger, a floating panel with the same row styling, a check mark on the selected option, closes on outside click / Esc, full keyboard and ARIA support.
- Rebuild the shared `DropdownFilter` (dashboard Branch picker, calendar toolbar, audit trail filters) and `SelectField` (~35 form usages across admin pages, invitation modals and visitor wizard) on top of it, keeping their props so call sites stay unchanged.
- Replace the remaining raw `<select>` elements (delegate picker in `DelegateInvitationModal`, "Assign to group" in the form builder's `SortableFieldRow`) with the same component.
- The panel renders in a portal with viewport-aware placement so it is not clipped by scrolling modals or overflow containers, and flips upward near the bottom edge.
- No behaviour, data or API changes; values, placeholders, disabled/error/required states keep working.

## Capabilities

### New Capabilities
- `themed-select-dropdowns`: the app-wide contract that single-value dropdowns use the themed panel instead of the native browser menu.

### Modified Capabilities
<!-- none: the board-filter requirements in admin-invitations / staff-dashboard are unchanged -->

## Impact

- Code: new `src/presentation/components/ui/SelectDropdown.tsx` (plus a small shared hook for open/close/outside-click/keyboard, reused by `MultiSelectFilter`); rewritten internals of `ui/DropdownFilter.tsx` and `ui/SelectField.tsx`; `DelegateInvitationModal.tsx`, `SortableFieldRow.tsx`.
- Tests/e2e that drive native selects (`selectOption`, `fireEvent.change` on a `<select>`) need updating to click-the-option.
- APIs and dependencies: none.
