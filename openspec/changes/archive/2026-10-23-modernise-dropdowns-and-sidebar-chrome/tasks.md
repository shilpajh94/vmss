## 1. Select primitive

- [x] 1.1 Add `src/presentation/components/ui/select-navigation.ts` with the pure functions `nextEnabledIndex`, `firstEnabled`, `lastEnabled`, `initialActiveIndex` and `typeaheadMatch` (500ms buffer reset), as described in design D3
- [x] 1.2 Add `tests/unit/select-navigation.test.ts` covering:
  - skipping disabled options;
  - wrap and clamp at the ends;
  - Home and End;
  - type-ahead (single character, multi-character buffer, cycling through repeated letters);
  - the initial active index, with and without a current value
- [x] 1.3 Add `src/presentation/components/ui/Select.tsx`:
  - a `<button role="combobox">` trigger (whole surface clickable) with an optional leading icon, a value or muted placeholder, and a rotating chevron;
  - a portal `<ul role="listbox">` panel using `usePresence` and `.motion-popover`;
  - full ARIA wiring per design D2
- [x] 1.4 Implement panel positioning per design D4: fixed position from `getBoundingClientRect`, min-width equal to the trigger, max-height clamp, flip above, re-measure on resize and capturing scroll, close when the trigger leaves the viewport, and a matching transform origin
- [x] 1.5 Implement interaction:
  - pointer toggle, outside-`pointerdown` close, option click selects;
  - keyboard: Enter, Space and the arrows to open; arrows, Home and End to move; type-ahead; Enter or Space to choose; Escape to cancel; Tab to close;
  - focus returns to the trigger, `onChange` fires once, and the selected option scrolls into view on open
- [x] 1.6 Apply the token-only styling from design D5, including the `md`/`sm` sizes, `tone="admin"`, the error and disabled states, dark mode, and 44px option rows below `sm`; confirm `npm run lint` (`check-theme-colors`) passes
- [x] 1.7 Mark the panel `data-select-panel`, and make the modal backdrop/outside-click handling ignore events inside it (check the shared modal component and `useFocusTrap`)

## 2. Migrate dropdowns

- [x] 2.1 Rewrite `SelectField.tsx` on top of `Select` with unchanged props; `placeholderSelectable` decides whether the placeholder is a real first option or only trigger text
- [x] 2.2 Rewrite `DropdownFilter.tsx` on top of `Select` (`size="sm"`, the icon inside the trigger, `ariaLabel` → `aria-label`, and the `sm:w-[200px]` sizing), which fixes the chevron dead zone
- [x] 2.3 Migrate the raw `<select>` in `DelegateInvitationModal.tsx`, keeping its loading/disabled placeholder text
- [x] 2.4 Migrate `SegmentedToggle.tsx`'s below-`sm` fallback `<select>`
- [x] 2.5 Migrate `FieldPropertiesPanel.tsx`'s field-type select, keeping the appended unknown-type option
- [x] 2.6 Migrate `SortableFieldRow.tsx`'s group select (`tone="admin"`, compact size, `UNGROUPED_VALUE` sentinel)
- [x] 2.7 Run `grep -rn "<select" src` and `grep -rn "new FormData" src` to confirm no native select is left and no form reads these values through `FormData`

## 3. Sidebar scrollbar

- [x] 3.1 Add `src/presentation/hooks/use-scroll-activity.ts`:
  - `data-scrolling`, set on scroll and cleared after 800ms;
  - `data-at-top` and `data-at-bottom`;
  - a `ResizeObserver` re-check;
  - a pure `edgeState(scrollTop, clientHeight, scrollHeight)` helper
- [x] 3.2 Add `tests/unit/scroll-edge-state.test.ts` for `edgeState` (fits, at top, middle, at bottom, sub-pixel rounding)
- [x] 3.3 Rewrite `.sidebar-nav-scroll` in `src/styles/index.css` per design D7:
  - the `@property --sidebar-thumb` fade;
  - a slim pill thumb that widens and brightens on hover;
  - hidden while idle;
  - `mask-image` and `-webkit-mask-image` edge fades keyed off `data-at-top` and `data-at-bottom`;
  - reduced-motion overrides
- [x] 3.4 Attach `useScrollActivity` to the `<nav>` in `AdminSidebar.tsx`, `DashboardSidebar.tsx` and `ReceptionSidebar.tsx`; check that items don't shift sideways when the thumb appears, both expanded and on the 72px rail

## 4. Collapse/expand toggle icons

- [x] 4.1 Add `CollapseSidebarIcon` (edge bar plus left-pointing double chevron) and `ExpandSidebarIcon` (edge bar plus right-pointing double chevron) to `icons.tsx`
- [x] 4.2 Update `SidebarHeader.tsx` to stack both icons with the rotate-and-cross-fade transition and `motion-reduce:transition-none`, keeping the existing `aria-label` and `aria-expanded`
- [x] 4.3 Add a hover/focus tooltip ("Collapse sidebar" / "Expand sidebar") to the toggle by reusing `useRailTooltip`
- [x] 4.4 Remove `PanelLeftCloseIcon` and `PanelLeftOpenIcon` if they have no remaining imports

## 5. E2E and verification

- [x] 5.1 Add a `choose_option(page, label, *, option_label=None, index=None)` helper to `e2e/conftest.py`, and replace every `select_option` call in `test_visitor_self_service.py`, `test_org_setup.py` and `test_invitation_lifecycle.py`
- [x] 5.2 Add e2e coverage in the targeted modules:
  - clicking a `DropdownFilter`'s chevron opens the list;
  - keyboard selection and Escape-cancel on a `SelectField`;
  - a dropdown inside the Delegate modal isn't clipped;
  - the sidebar toggle's icon and label change on collapse and expand
- [x] 5.3 Run `npm run lint`, `npm run build` (type check), `npm test`, and only the touched e2e modules (no full suite); fix any failures
- [x] 5.4 Manual check in light and dark modes at 375px, 768px and 1440px: dropdown look and flip, the admin sidebar's long nav scrollbar fade and edge fades, the toggle icon animation, and the reduced-motion preference
