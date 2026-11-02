## Context

- **Dropdowns.** All dropdowns are native `<select>` elements, spread across two shared wrappers and four raw instances:
  - `SelectField` (about 29 call sites, including the visitor wizard via `DynamicField`);
  - `DropdownFilter` (about 12 filter-bar call sites);
  - raw `<select>`s in `DelegateInvitationModal`, `SegmentedToggle` (mobile fallback below `sm`), `FieldPropertiesPanel` and `SortableFieldRow`.
- **The chevron bug.** `DropdownFilter` lays out `[icon][select flex-1][chevron]` as flex siblings inside a bordered `div`. The chevron has `pointer-events-none`, so a click on it falls through to the wrapper `div` and never reaches the `<select>`. The same happens for clicks on the icon and the padding.
- **Existing popover infrastructure** to reuse:
  - `usePresence` (mount, `data-state` open/closing, unmount after exit);
  - the `.motion-popover` keyframes in `index.css`;
  - `useRailTooltip`'s portal plus `getBoundingClientRect` positioning (`SidebarNavItem.tsx`);
  - shadow and border tokens from `ThemeModeMenu` and `NotificationBell`.
- **Sidebar scrolling.** The `<nav className="sidebar-nav-scroll …overflow-y-auto">` is in `AdminSidebar`, `DashboardSidebar` and `ReceptionSidebar`. `.sidebar-nav-scroll` gives a static 6px always-on thumb. `theme.css` already has a `scrollbar-autohide` utility for light surfaces.
- **Collapse toggle.** `SidebarHeader` swaps `PanelLeftCloseIcon` and `PanelLeftOpenIcon`. They are both the same framed panel with a 3px arrow flipped.
- **Testing.** Unit tests run on `node --test` over `.ts` files only, with no DOM renderer. Playwright e2e exists (`npm run e2e`). Lint includes `check-theme-colors.mjs`, so colours must come from theme tokens.

## Goals / Non-Goals

**Goals:**
- One `Select` primitive that owns the look, hit area, keyboard model, ARIA and positioning. `SelectField` and `DropdownFilter` become thin wrappers with **unchanged props**, so call sites don't change.
- Fix the chevron and icon dead zones by making the entire trigger a single `<button>`.
- Add an auto-hiding, animated sidebar scrollbar with scroll-edge fades, and two clearly distinct, animated collapse and expand icons.

**Non-Goals:**
- Multi-select, searchable or filterable comboboxes, async option loading, and option groups.
- Restyling native date and time inputs.
- Changing any other page's scrollbars (`scrollbar-thin` and `scrollbar-autohide` stay as they are).
- Any API change.

## Decisions

### D1. Build an in-house `Select` and don't add a library
Radix, Headless UI and React Aria would each add a dependency and their own styling and portal conventions. They would also duplicate `usePresence` and `.motion-popover`, which already define how this app animates popovers. A single-select listbox is a small, well-specified pattern (the WAI-ARIA "select-only combobox"). Building it ourselves keeps the bundle and the motion system consistent.

### D2. Use the ARIA select-only combobox pattern, with focus kept on the trigger
- **Trigger:** a `<button type="button" role="combobox">` with `aria-haspopup="listbox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `aria-labelledby` (the visible label) and `aria-required`/`aria-invalid`/`aria-describedby`.
- **Panel:** `<ul role="listbox">` containing `<li role="option" aria-selected aria-disabled>`.
- **Focus:** stays on the trigger the whole time. The active option is tracked through `aria-activedescendant`, so Tab, Escape and focus return work naturally, without moving focus into a portal.

### D3. Keep the keyboard and type-ahead logic in a pure module
`select-navigation.ts` will contain only pure functions:
- `nextEnabledIndex(options, from, delta)`, which skips disabled options;
- `firstEnabled` and `lastEnabled`;
- `typeaheadMatch(options, buffer, from)`, with a buffer that resets after 500ms of no typing;
- `initialActiveIndex(options, value)`.

This makes the behaviour unit-testable under the existing `node --test` runner. The `.tsx` component only wires events to these functions.

### D4. Render the panel in a portal with fixed positioning and flip
The panel renders into `document.body` with `position: fixed`. It is positioned from the trigger's `getBoundingClientRect()`:
- `min-width` is the trigger width, and `max-height` is about 280px or the available space, whichever is smaller.
- It opens below the trigger, or **above** when the space below is under 200px and the space above is larger.
- It is re-measured on `resize` and on capturing `scroll` events.
- It closes if the trigger leaves the viewport.

This is the same approach `useRailTooltip` uses. A portal is required because several dropdowns sit in modals, cards and the form-builder panel with `overflow: hidden/auto`.

The transform origin follows the side the panel opens on (`origin-top` or `origin-bottom`), so `.motion-popover` scales from the trigger.

The panel's `z-index` sits above modals. The modal's focus trap has to tolerate it. Because focus stays on the trigger (D2), `useFocusTrap` is not affected.

Clicking outside closes the panel. This is a `pointerdown` listener on the document that ignores the trigger and the panel.

### D5. Visual specification (tokens only)
- **Trigger:**
  - `h-10` (or `min-h-10` where the field is already that size), `rounded-lg`, `border-border`, `bg-surface`, `px-3`, `text-body`;
  - hover `border-border-strong`, focus-visible `ring-2 ring-secondary-accent`, open state `border-secondary-accent`;
  - error `border-danger`, disabled `opacity-60 cursor-not-allowed`;
  - placeholder `text-text-muted`;
  - the chevron rotates 180° when open (`transition-transform duration-standard`).
- **Panel:**
  - `rounded-xl border border-border bg-surface p-1`;
  - the existing popover shadow, `overflow-y-auto scrollbar-thin`.
- **Option:**
  - `rounded-md px-2.5 py-2 text-body`;
  - active/hover `bg-secondary-accent-soft`;
  - selected `font-semibold` with a trailing `CheckIcon` in `text-secondary-accent`;
  - disabled `opacity-50`.
- **Admin-accent screens:** these currently use `focus:ring-admin-accent` (`SortableFieldRow`). They pass `tone="admin"`, which swaps the accent tokens.
- **Size variants:** `md` (default) and `sm` (`DropdownFilter`'s 13px semibold text, and `SortableFieldRow`'s compact `md:text-xs`). Below `sm` (640px), the trigger text stays at 16px (`max-sm:text-base`) so mobile Safari doesn't zoom in, which matches the current classes.

### D6. Wrappers keep their contracts
- **`SelectField`:** the same props. `placeholderSelectable` decides whether the placeholder is rendered as a first `{value: '', label: placeholder}` option, or appears only as the empty-trigger text.
- **`DropdownFilter`:** keeps its `icon`, `ariaLabel` and `sm:w-[200px]` sizing. The icon moves *inside* the trigger button. With no visible label, `ariaLabel` becomes `aria-label`.
- **`SegmentedToggle`'s mobile fallback, `DelegateInvitationModal`, `FieldPropertiesPanel` and `SortableFieldRow`:** these switch to `Select` directly. Each keeps its existing value and onChange semantics, including the `UNGROUPED_VALUE` sentinel and the "unknown field type appended" option.

**Alternative considered: keep a native `<select>` and only restyle the closed trigger** (an overlay chevron and `appearance-none`). This fixes the dead zone cheaply. It was rejected because the user explicitly asked for a product-style dropdown, and the native option list can't be styled.

### D7. Overlay scrollbar for the sidebar
`.sidebar-nav-scroll` is rewritten as follows.

- **Scrollbar styling:**
  - Firefox: `scrollbar-width: thin`, with `scrollbar-color` switching from `transparent` to `rgb(255 255 255 / .22)` when `[data-scrolling]`, `:hover` or `:focus-within` applies.
  - WebKit: an 8px transparent `::-webkit-scrollbar`, with a thumb of `border: 2px solid transparent; background-clip: padding-box; border-radius: 9999px`. That gives a slim 4px pill, which "widens" to 6px on `:hover` by shrinking the border, and brightens to `/.38`.
  - The thumb colour is driven by a registered custom property (`@property --sidebar-thumb`, `<color>`), so it **transitions** (fades) instead of snapping. WebKit can't transition the scrollbar's own `background-color`, but it does repaint as an animated custom property changes.
- **`useScrollActivity(ref)` hook:**
  - sets `data-scrolling` on scroll and removes it 800ms after the last scroll event;
  - sets `data-at-top` and `data-at-bottom` from `scrollTop`, `clientHeight` and `scrollHeight`;
  - re-checks on a `ResizeObserver` when the list's height changes, for example after a role-based menu loads.
- **Edge fades:** a `mask-image: linear-gradient(...)` on the `<nav>`, with 16px fade stops toggled by `:not([data-at-top])` and `:not([data-at-bottom])`. A mask fades into whatever background is behind the list, so no extra overlay elements are needed and clicks pass through. When the list fits, both attributes are present and no mask is applied.
- **No layout shift:** the scrollbar is overlaid by keeping the existing right padding, with `scrollbar-gutter: stable` *not* set on the nav. The 8px track already lies within the nav's existing padding, so items don't shift when the thumb shows.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` drops the transitions.

The hook lives in `src/presentation/hooks/use-scroll-activity.ts`. The three sidebars attach it to their `<nav>`. Its pure "edge state from metrics" helper is unit-tested.

### D8. Distinct collapse and expand icons with an animated swap
Two new icons are added to `icons.tsx`, drawn in the existing lucide-style 24×24 stroke-2 style:
- `CollapseSidebarIcon`: a double chevron pointing left (`«`) beside a vertical bar at the left edge, meaning "fold into the edge".
- `ExpandSidebarIcon`: a vertical bar at the left edge with a double chevron pointing right (`»`), meaning "open out".

The arrow direction and position are clearly opposite, rather than one small flipped arrow inside the same frame.

`SidebarHeader` renders **both** icons, stacked in the same 18px box. The inactive icon is `opacity-0 rotate-90 scale-75`, the active one is `opacity-100 rotate-0 scale-100`, and both use `transition duration-standard ease-motion-out`. This produces a rotate-and-cross-fade timed with `SidebarFrame`'s width transition. `motion-reduce:transition-none` makes the swap instant. Both SVGs stay `aria-hidden`, and the button keeps its existing `aria-label` and `aria-expanded`. The button also gets a hover/focus tooltip by reusing `useRailTooltip(label, true)`. `PanelLeftCloseIcon` and `PanelLeftOpenIcon` are removed if nothing else imports them.

## Risks / Trade-offs

- **Some native behaviour is lost:** the OS wheel picker on iOS and Android, and the browser's built-in form autofill into a `<select>`. This is mitigated by mobile-friendly sizing (44px option rows below `sm`) and a panel that scrolls. Autofill into these app dropdowns isn't relied on anywhere.
- **The portal inside a modal:** an outside-click on the panel could be read by the modal as a backdrop click. The modal's backdrop handler must ignore events whose target is inside an element marked `[data-select-panel]`. This needs a check against every modal that contains a dropdown (Delegate, Edit Invitation, Export, Branch form, Floor modal, Add field).
- **Form semantics:** a button-based select doesn't take part in native `<form>` submission or `required` validation. All current forms are controlled React state with their own validation, so nothing reads `FormData` from these. Implementation will confirm with a grep for `new FormData`.
- **Animating the scrollbar colour:** `@property` animation of scrollbar colours works in Chromium and Safari 16.4+. Elsewhere, the thumb shows and hides without the fade, which is acceptable.
- **Mask edge fades** need `-webkit-mask-image` for Safari. Both prefixed and unprefixed declarations are included.
- **E2E selectors:** the Playwright e2e suite calls `get_by_label(...).select_option(...)` in `test_visitor_self_service.py`, `test_org_setup.py` and `test_invitation_lifecycle.py`. Playwright only supports that call on a native `<select>`, so those steps will break. A shared `choose_option(page, label, *, option_label=None, index=None)` helper in `e2e/conftest.py` will click the combobox and then the matching `role="option"`, and every `select_option` call moves to it. The unit tests don't touch selects.
