## Why

QA found two polish problems in the staff and admin UI. First, dropdowns don't match the design and have a broken hit area. Every dropdown renders the browser's native `<select>`. Its option list looks different on every OS and can't be themed. On filter dropdowns (`DropdownFilter`), clicking the chevron does nothing, because the chevron is a sibling of the `<select>` rather than part of it, so only the text area in the middle opens the list. Second, the sidebar's scrollable navigation works, but its scrollbar is a static grey strip that always shows. The collapse/expand toggle uses two nearly identical "panel" icons that differ only by a 3px arrow, so users can't tell which state they're in at a glance.

## What Changes

- Add one shared, accessible custom **Select** control (a combobox button plus an animated listbox popover). It replaces the native `<select>` in `SelectField`, `DropdownFilter`, and the four hand-rolled `<select>` elements (`DelegateInvitationModal`, `SegmentedToggle`'s mobile fallback, `FieldPropertiesPanel`, `SortableFieldRow`).
- Restyle dropdowns to a product-style look built on the design tokens: a rounded trigger with a hover/focus state, a chevron that rotates when the list opens, and a floating panel with soft shadow and rounded corners. Options get a hover/active highlight, the selected option shows a check mark, and the placeholder is styled as muted text. Light and dark themes are both supported.
- Fix the hit area: clicking anywhere on the trigger opens the list, including the chevron, the leading icon and the padding.
- Support full keyboard use (arrow keys, Home/End, Enter/Space, Escape, Tab, and type-ahead to jump to an option). Lists that run past their maximum height scroll. The panel flips above the trigger when there's no room below and is never clipped by a modal or card that hides its overflow.
- Replace the sidebar navigation scrollbar with a modern auto-hiding overlay scrollbar. It shows a thin thumb only while the list is hovered, focused or actively scrolled. The thumb widens on hover and fades out after scrolling stops. Soft top and bottom fade edges show that more items are above or below. Users who prefer reduced motion get the same behaviour without the animation.
- Give the collapse toggle two clearly different icons, one per state, with an animated swap between them. Expanded, the toggle shows a "collapse" icon (chevrons pointing left, toward the edge). Collapsed, it shows an "expand" icon (chevrons pointing right). The swap is a short rotate and cross-fade, not an instant change.

## Capabilities

### New Capabilities
- `select-dropdowns`: the look, hit area, keyboard behaviour, positioning and accessibility contract that every single-choice dropdown in the web app must meet. This covers the staff, reception, admin and visitor-portal screens, since the visitor wizard renders through `SelectField`/`DynamicField` too.

### Modified Capabilities
- `app-shell`: two requirements change. "Sidebar and top navigation remain fixed while content scrolls independently" now requires an auto-hiding, animated sidebar scrollbar with scroll-edge fades instead of a merely dark-themed one. "Desktop sidebar can be collapsed to an icon rail" now requires visually distinct collapse and expand icons with an animated transition.

## Impact

- **Code (VMMS_WEB only; no API change):**
  - New `src/presentation/components/ui/Select.tsx`.
  - Rewritten `SelectField.tsx` and `DropdownFilter.tsx`, with the same props, so the roughly 40 call sites don't change.
  - The four raw `<select>` elements are migrated.
  - New `CollapseSidebarIcon` and `ExpandSidebarIcon` in `icons.tsx`.
  - Changes to `SidebarHeader.tsx`, the three sidebars' `<nav>` (scroll-fade wrapper), and the `.sidebar-nav-scroll` styles in `index.css`.
- **Dependencies:** none added. The listbox is built in-house on the existing `usePresence` hook and the `motion-popover` animation.
- **Tests:** no existing unit or e2e test drives a native `<select>`. New unit tests cover the Select's keyboard and pointer behaviour.
- **Out of scope:** multi-select and searchable or async comboboxes, and the visitor-facing native date and time pickers.
