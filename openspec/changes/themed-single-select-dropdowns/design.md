## Context

`MultiSelectFilter` (board filters) is already the target look. All other dropdowns are native `<select>`: `DropdownFilter` (dashboard branch, calendar, audit), `SelectField` (used ~35 times), and two raw selects (`DelegateInvitationModal`, `SortableFieldRow`). `Modal` body uses `overflow-y-auto`, so an absolutely positioned panel inside it would be clipped. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One reusable single-select that visually and behaviourally matches `MultiSelectFilter`.
- Zero call-site churn for `SelectField` and `DropdownFilter` (same props).
- Panel never clipped by modals/scroll containers.

**Non-Goals:**
- Search/typeahead filtering or multi-select in forms (`AutocompleteField` stays as is).
- Changing the board multi-select behaviour or any data/API.
- Restyling text inputs or other controls.

## Decisions

1. **New `ui/SelectDropdown.tsx`** (headless-ish: trigger render variants `filter` | `field`, `options`, `value`, `onChange`, `placeholder`, `disabled`, `error`, `ariaLabel`, `placeholderSelectable`). `DropdownFilter` and `SelectField` become thin wrappers. Alternative: generalise `MultiSelectFilter` with a `multiple` flag — rejected, it mixes two ARIA models and checkbox vs check-mark rows.
2. **Shared hook `use-dropdown-panel`** for open state, outside pointerdown, Esc/Tab, active index and arrow/Home/End/typeahead handling; `MultiSelectFilter` is migrated to it so both stay identical. Alternative: copy the logic — rejected, drift risk.
3. **Portal + fixed positioning**: render the panel in `document.body`, positioned from the trigger's `getBoundingClientRect()` (min-width = trigger width), recomputed on scroll/resize while open, flipping above when space below is smaller than the panel's max height (~16rem). Alternative: `position:absolute` inside the trigger — rejected, clipped in `Modal`. Outside-click detection must treat the portal panel as inside.
4. **Prompt placeholder**: for `SelectField`, the empty "Select" entry is shown on the trigger only; it is a listed row only when `placeholderSelectable` (matches today's native `disabled` option).
5. **Mobile**: 16px text and `min-h-10`/row padding as in existing `max-sm`/`max-lg` classes, to avoid iOS zoom.
6. **Tokens only**: reuse existing Tailwind theme tokens (`border-border`, `bg-surface`, `bg-surface-muted`, `text-admin-accent`, etc.) — no new colours.
7. **Tests**: native-select interactions in unit/e2e tests become click trigger → click `role="option"`.

## Risks / Trade-offs

- [Native select gave free mobile pickers/autofill] → accepted for consistency; touch sizing and 16px text kept.
- [Portal panel inside a modal and focus trapping/outside-click of the modal] → panel stops pointerdown propagation correctly and closes on Esc without closing the modal (stopPropagation on Esc while open).
- [Wide blast radius (~35 usages)] → props unchanged; verify key forms (branch, visitor wizard, form builder) manually.
- [Stale test selectors] → grep and update during implementation.
